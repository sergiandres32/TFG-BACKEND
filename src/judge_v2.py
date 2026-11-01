"""
judge_v2.py: Versión mejorada de judge con soporte para verdicts detallados (AC/WA/TLE/CE/RTE/OOM)
Diseñado para ser integrado en API y CLI.
"""

import json
import base64
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List, Tuple
from enum import Enum


MAX_TEST_FILE_BYTES = 5 * 1024 * 1024
MAX_TEST_FILES_TOTAL_BYTES = 20 * 1024 * 1024
MAX_TEST_FILE_COUNT = 20
MAX_CAPTURED_FILE_BYTES = 512 * 1024
MAX_CAPTURED_RUN_BYTES = 4 * 1024 * 1024


class Verdict(str, Enum):
    AC = "AC"     # Accepted
    WA = "WA"     # Wrong Answer
    CE = "CE"     # Compile Error
    TLE = "TLE"   # Time Limit Exceeded
    RTE = "RTE"   # Runtime Error
    OOM = "OOM"   # Out of Memory


def compile_with_gcc(source_code: str, output_path: str) -> Tuple[bool, str]:
    """Compila código C, retorna (success, message)."""
    try:
        import tempfile as tf
        with tf.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as f:
            f.write(source_code)
            source_file = f.name
        
        cmd = ["gcc", source_file, "-o", output_path]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        os.unlink(source_file)
        
        success = proc.returncode == 0
        message = proc.stdout + proc.stderr
        return success, message
    except subprocess.TimeoutExpired:
        return False, "Compilation timeout"
    except Exception as e:
        return False, str(e)


def run_executable(
    exec_path: str,
    input_data: str | bytes,
    timeout: int = 5,
    args: List[str] = None,
    cwd: str = None,
) -> Dict[str, Any]:
    """
    Ejecuta binario con input y argumentos de linea de comandos (args), retorna dict
    con stdout/stderr/exit_code/timed_out/time. Detecta OOM en contexto Docker (killed por OOMKiller).
    """
    try:
        start = time.time()
        input_bytes = input_data if isinstance(input_data, bytes) else (input_data or "").encode("utf-8")
        # Capture bytes and decode with replacement to avoid decoding exceptions
        proc = subprocess.run(
            [exec_path, *(args or [])],
            input=input_bytes,
            capture_output=True,
            timeout=timeout,
            cwd=cwd,
        )
        duration = time.time() - start
        try:
            stdout = proc.stdout.decode('utf-8', errors='replace') if isinstance(proc.stdout, (bytes, bytearray)) else str(proc.stdout)
        except Exception:
            stdout = ''
        try:
            stderr = proc.stderr.decode('utf-8', errors='replace') if isinstance(proc.stderr, (bytes, bytearray)) else str(proc.stderr)
        except Exception:
            stderr = ''
        # En entornos con limites de memoria, el proceso puede morir con -9/137
        # sin lanzar excepcion de Python. Lo marcamos como posible OOM.
        oom_killed = proc.returncode in (-9, 137)
        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": proc.returncode,
            "timed_out": False,
            "oom_killed": oom_killed,
            "time": duration,
        }
    except subprocess.TimeoutExpired as e:
        # e.stdout/e.stderr may be bytes
        stdout = ''
        stderr = ''
        try:
            if getattr(e, 'stdout', None) is not None:
                stdout = e.stdout.decode('utf-8', errors='replace') if isinstance(e.stdout, (bytes, bytearray)) else str(e.stdout)
        except Exception:
            stdout = ''
        try:
            if getattr(e, 'stderr', None) is not None:
                stderr = e.stderr.decode('utf-8', errors='replace') if isinstance(e.stderr, (bytes, bytearray)) else str(e.stderr)
        except Exception:
            stderr = ''
        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": -1,
            "timed_out": True,
            "oom_killed": False,
            "time": timeout,
        }
    except Exception as e:
        # Posible OOM kill (exit code 137 en Docker = killed by OOMKiller)
        return {
            "stdout": "",
            "stderr": str(e),
            "exit_code": 137,
            "timed_out": False,
            "oom_killed": True,
            "time": timeout,
        }


def decode_test_files(files: Dict[str, Any] | None) -> Dict[str, bytes]:
    """Decode an optional mapping of relative paths to UTF-8 or base64 content."""
    if files is None:
        return {}
    if not isinstance(files, dict):
        raise ValueError("Test files must be an object mapping paths to content")
    if len(files) > MAX_TEST_FILE_COUNT:
        raise ValueError(f"A test case may define at most {MAX_TEST_FILE_COUNT} files")

    decoded: Dict[str, bytes] = {}
    total_size = 0
    for raw_path, value in files.items():
        path = str(raw_path).replace("\\", "/")
        parts = path.split("/")
        if not path or path.startswith("/") or any(part in ("", ".", "..") for part in parts) or "\x00" in path:
            raise ValueError(f"Invalid test file path: {raw_path}")
        if isinstance(value, str):
            content = value.encode("utf-8")
        elif isinstance(value, dict):
            data = value.get("data", "")
            encoding = value.get("encoding", "utf-8")
            if not isinstance(data, str):
                raise ValueError(f"Invalid content for test file: {raw_path}")
            if encoding == "utf-8":
                content = data.encode("utf-8")
            elif encoding == "base64":
                try:
                    content = base64.b64decode(data, validate=True)
                except Exception as exc:
                    raise ValueError(f"Invalid base64 for test file: {raw_path}") from exc
            else:
                raise ValueError(f"Unsupported encoding for test file: {encoding}")
        else:
            raise ValueError(f"Invalid content for test file: {raw_path}")

        if len(content) > MAX_TEST_FILE_BYTES:
            raise ValueError(f"Test file too large: {raw_path}")
        total_size += len(content)
        if total_size > MAX_TEST_FILES_TOTAL_BYTES:
            raise ValueError("Test files exceed the total size limit")
        decoded[path] = content
    return decoded


def stage_test_files(files: Dict[str, bytes], cwd: str) -> None:
    """Write decoded fixtures below a fresh test working directory."""
    root = os.path.realpath(cwd)
    for relative_path, content in files.items():
        parts = relative_path.split("/")
        target = os.path.realpath(os.path.join(root, *parts))
        if not target.startswith(root + os.sep):
            raise ValueError(f"Test file path escapes working directory: {relative_path}")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as output_file:
            output_file.write(content)


def collect_and_compare_files(
    test: Dict[str, Any], cwd: str, remaining_capture_bytes: int = MAX_CAPTURED_RUN_BYTES
) -> Tuple[Dict[str, bytes], List[str]]:
    expected_files = decode_test_files(test.get("expected_files"))
    output_paths = test.get("output_files")
    if output_paths is None:
        output_paths = list(expected_files)
    if not isinstance(output_paths, list):
        raise ValueError("output_files must be a list of relative paths")

    requested_paths = list(dict.fromkeys([*expected_files, *[str(path) for path in output_paths]]))
    if len(requested_paths) > MAX_TEST_FILE_COUNT:
        raise ValueError(f"A test case may collect at most {MAX_TEST_FILE_COUNT} output files")
    decode_test_files({path: "" for path in requested_paths})
    root = os.path.realpath(cwd)
    captured: Dict[str, bytes] = {}
    mismatches: List[str] = []

    for relative_path in requested_paths:
        target = os.path.join(root, *relative_path.split("/"))
        resolved = os.path.realpath(target)
        if not resolved.startswith(root + os.sep) or os.path.islink(target) or not os.path.isfile(target):
            if relative_path in expected_files:
                mismatches.append(f"Expected output file missing: {relative_path}")
            continue

        size = os.path.getsize(target)
        capture_limit = min(MAX_CAPTURED_FILE_BYTES, max(0, remaining_capture_bytes - sum(map(len, captured.values()))))
        if size > capture_limit:
            mismatches.append(f"Output file exceeds capture limit: {relative_path}")
            continue
        with open(target, "rb") as output_file:
            actual = output_file.read(capture_limit + 1)
        if len(actual) > capture_limit:
            mismatches.append(f"Output file exceeds capture limit: {relative_path}")
            continue
        captured[relative_path] = actual
        expected = expected_files.get(relative_path)
        if expected is not None and actual != expected:
            mismatches.append(f"Output file differs: {relative_path}")

    return captured, mismatches


def encode_captured_files(files: Dict[str, bytes]) -> List[Dict[str, str]]:
    return [
        {"path": path, "encoding": "base64", "data": base64.b64encode(content).decode("ascii")}
        for path, content in files.items()
    ]


MAX_CAPTURED_OUTPUT_CHARS = 64 * 1024


def build_output_entry(test_id: str, run_result: Dict[str, Any]) -> Dict[str, Any]:
    """Salida capturada de un test (solo para profesor; nunca va en results/details)."""
    def clip(text: str) -> str:
        text = text or ""
        if len(text) > MAX_CAPTURED_OUTPUT_CHARS:
            return text[:MAX_CAPTURED_OUTPUT_CHARS] + "\n[...truncated...]"
        return text

    return {
        "test_id": test_id,
        "stdout": clip(run_result.get("stdout", "")),
        "stderr": clip(run_result.get("stderr", "")),
        "exit_code": run_result.get("exit_code"),
    }


def resolve_args(tests_obj: Dict[str, Any], test: Dict[str, Any]) -> List[str]:
    """Args del ejercicio (siempre) seguidos de los args propios del test case."""
    return [str(a) for a in (tests_obj.get("exercise_args") or [])] + [str(a) for a in (test.get("args") or [])]


def normalize_text(s: str, ignore_whitespace: bool) -> str:
    """Normaliza texto para comparación."""
    if ignore_whitespace:
        return " ".join(s.split())
    return s


def evaluate_test(actual_output: str, test: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evalúa un test individual.
    Retorna: {"passed": bool, "verdict_detail": "..."}
    """
    mode = test.get("mode", "exact")
    ignore_ws = bool(test.get("ignore_whitespace", False))

    if mode == "regex":
        pattern = test.get("expected_pattern") or test.get("expected")
        if not pattern:
            return {"passed": False, "verdict_detail": "No regex pattern provided"}
        try:
            m = re.search(pattern, actual_output, flags=re.MULTILINE)
            return {
                "passed": bool(m),
                "verdict_detail": "Regex matched" if m else "Regex no match"
            }
        except re.error as e:
            return {"passed": False, "verdict_detail": f"Invalid regex: {e}"}

    elif mode == "exact":
        expected = test.get("expected")
        if expected is None:
            return {"passed": False, "verdict_detail": "No expected text"}
        
        out_norm = normalize_text(actual_output, ignore_ws)
        exp_norm = normalize_text(expected, ignore_ws)
        matched = out_norm == exp_norm
        return {
            "passed": matched,
            "verdict_detail": "Exact match" if matched else f"Mismatch"
        }

    elif mode == "lines":
        expected = test.get("expected")
        if expected is None:
            return {"passed": False, "verdict_detail": "No expected text"}
        
        out_lines = [normalize_text(l, ignore_ws) for l in actual_output.splitlines()]
        exp_lines = [normalize_text(l, ignore_ws) for l in expected.splitlines()]
        matched = out_lines == exp_lines
        return {
            "passed": matched,
            "verdict_detail": "Lines match" if matched else f"Lines differ"
        }

    elif mode in ("unordered_lines", "unordered_tokens"):
        expected = test.get("expected")
        if expected is None:
            return {"passed": False, "verdict_detail": "No expected text"}

        if mode == "unordered_lines":
            out_items = [normalize_text(l, ignore_ws) for l in actual_output.splitlines()]
            exp_items = [normalize_text(l, ignore_ws) for l in expected.splitlines()]
        else:
            out_items = actual_output.split()
            exp_items = expected.split()
        # Multiset: ignora el orden pero respeta duplicados
        matched = sorted(out_items) == sorted(exp_items)
        return {
            "passed": matched,
            "verdict_detail": "Unordered match" if matched else "Unordered mismatch"
        }

    return {"passed": False, "verdict_detail": f"Unknown mode: {mode}"}


def run_and_evaluate_all_tests(
    source_code: str,
    tests_obj: Dict[str, Any],
    timeout: int = 5,
    workdir: str = None
) -> Dict[str, Any]:
    """
    Orquesta compilación, ejecución y evaluación contra todos los tests.
    
    Retorna dict con:
    {
        "verdict": "AC" | "WA" | "CE" | "TLE" | "RTE" | "OOM",
        "passed_all": bool,
        "results": [
            {"test_id": "t1", "passed": true, "details": "..."},
            ...
        ],
        "compile_error": null | "string",
        "duration_ms": int
    }
    """
    start_time = time.time()
    workdir = workdir or tempfile.mkdtemp(prefix="judge_")
    exe_path = os.path.join(workdir, "submission")
    
    try:
        # === Compilación ===
        success, compile_msg = compile_with_gcc(source_code, exe_path)
        if not success:
            duration = int((time.time() - start_time) * 1000)
            return {
                "verdict": Verdict.CE.value,
                "passed_all": False,
                "results": [],
                "compile_error": compile_msg,
                "duration_ms": duration,
            }
        
        # === Ejecución y evaluación ===
        results = []
        outputs = []
        captured_total = 0
        all_passed = True
        has_tle = False
        has_rte = False
        has_oom = False

        for test_index, test in enumerate(tests_obj.get("tests", [])):
            test_id = test.get("id") or test.get("name") or "unnamed"
            input_data = test.get("input", "")
            args = resolve_args(tests_obj, test)
            case_dir = os.path.join(workdir, f"case_{test_index}")
            os.makedirs(case_dir, exist_ok=True)
            case_executable = os.path.join(case_dir, "submission")
            shutil.copy2(exe_path, case_executable)
            stage_test_files(decode_test_files(test.get("input_files")), case_dir)

            # Ejecutar
            run_result = run_executable(case_executable, input_data, timeout=timeout, args=args, cwd=case_dir)
            captured_files, file_errors = collect_and_compare_files(
                test, case_dir, MAX_CAPTURED_RUN_BYTES - captured_total
            )
            captured_total += sum(map(len, captured_files.values()))
            output_entry = build_output_entry(test_id, run_result)
            output_entry["files"] = encode_captured_files(captured_files)
            outputs.append(output_entry)
            
            # Detectar OOM
            if run_result.get("oom_killed"):
                has_oom = True
                results.append({
                    "test_id": test_id,
                    "passed": False,
                    "details": "Out of Memory"
                })
                all_passed = False
                continue
            
            # Detectar TLE
            if run_result.get("timed_out"):
                has_tle = True
                results.append({
                    "test_id": test_id,
                    "passed": False,
                    "details": "Time Limit Exceeded"
                })
                all_passed = False
                continue
            
            # Detectar RTE (exit code != 0, no TLE/OOM)
            if run_result.get("exit_code") != 0:
                has_rte = True
                results.append({
                    "test_id": test_id,
                    "passed": False,
                    "details": f"Runtime Error (exit code {run_result['exit_code']})"
                })
                all_passed = False
                continue
            
            # Evaluar output
            eval_result = evaluate_test(run_result.get("stdout", ""), test)
            if file_errors:
                eval_result["passed"] = False
                eval_result["verdict_detail"] = "; ".join(
                    filter(None, [eval_result.get("verdict_detail"), *file_errors])
                )
            if not eval_result.get("passed"):
                all_passed = False
            
            results.append({
                "test_id": test_id,
                "passed": eval_result.get("passed"),
                "details": eval_result.get("verdict_detail")
            })
        
        # Determinar verdict final
        if all_passed and len(results) > 0:
            verdict = Verdict.AC.value
        elif has_oom:
            verdict = Verdict.OOM.value
        elif has_tle:
            verdict = Verdict.TLE.value
        elif has_rte:
            verdict = Verdict.RTE.value
        else:
            verdict = Verdict.WA.value
        
        duration = int((time.time() - start_time) * 1000)
        return {
            "verdict": verdict,
            "passed_all": all_passed,
            "results": results,
            "outputs": outputs,
            "compile_error": None,
            "duration_ms": duration,
        }
    
    finally:
        # Limpieza
        try:
            shutil.rmtree(workdir)
        except Exception:
            pass


if __name__ == "__main__":
    # Demo simple
    test_code = """
#include <stdio.h>
int main() {
    int a, b;
    scanf("%d %d", &a, &b);
    printf("%d\\n", a + b);
    return 0;
}
"""
    
    tests = {
        "tests": [
            {"id": "test1", "input": "1 2\n", "expected": "3\n", "mode": "exact"},
            {"id": "test2", "input": "5 5\n", "expected": "10\n", "mode": "exact"},
        ]
    }
    
    result = run_and_evaluate_all_tests(test_code, tests, timeout=5)
    print(json.dumps(result, ensure_ascii=False, indent=2))
