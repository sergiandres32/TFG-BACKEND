"""
judge_v2.py: Versión mejorada de judge con soporte para verdicts detallados (AC/WA/TLE/CE/RTE/OOM)
Diseñado para ser integrado en API y CLI.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List, Tuple
from enum import Enum


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


def run_executable(exec_path: str, input_data: str, timeout: int = 5) -> Dict[str, Any]:
    """
    Ejecuta binario con input, retorna dict con stdout/stderr/exit_code/timed_out/time.
    Detecta OOM en contexto Docker (killed por OOMKiller).
    """
    try:
        start = time.time()
        # Capture bytes and decode with replacement to avoid decoding exceptions
        proc = subprocess.run(
            [exec_path],
            input=input_data.encode('utf-8'),
            capture_output=True,
            timeout=timeout
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
        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": proc.returncode,
            "timed_out": False,
            "oom_killed": False,
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
        all_passed = True
        has_tle = False
        has_rte = False
        has_oom = False
        
        for test in tests_obj.get("tests", []):
            test_id = test.get("id") or test.get("name") or "unnamed"
            input_data = test.get("input", "")
            
            # Ejecutar
            run_result = run_executable(exe_path, input_data, timeout=timeout)
            
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
