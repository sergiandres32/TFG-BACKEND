#!/usr/bin/env python3
import sys
import json
from pathlib import Path

# Ensure /judge is in path when running inside container
if "/judge" not in sys.path:
    sys.path.insert(0, "/judge")

from src import judge_v2
import subprocess
import tempfile
import os


def main(argv):
    if len(argv) < 2:
        print("Usage: judge_container_runner.py <code_path> <tests_json_path>")
        return 2

    code_path = argv[0]
    tests_path = argv[1]

    try:
        code = Path(code_path).read_text()
    except Exception as e:
        print(json.dumps({"error": f"cannot read code: {e}"}))
        return 3

    try:
        tests = json.loads(Path(tests_path).read_text())
    except Exception as e:
        print(json.dumps({"error": f"cannot read tests: {e}"}))
        return 4

    result = judge_v2.run_and_evaluate_all_tests(code, tests, timeout=5)
    print(json.dumps(result, ensure_ascii=False))

    # Extra debug: if env JUDGE_DEBUG=1 or '--debug' arg given, and there is an OOM, try local compile+run details
    debug = os.getenv("JUDGE_DEBUG") == "1" or (len(argv) > 2 and argv[2] == "--debug")
    if debug and (result.get("verdict") == "OOM" or any(r.get("details") == "Out of Memory" for r in result.get("results", []))):
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as sf:
                sf.write(code)
                src_path = sf.name
            bin_path = src_path + ".out"
            compile_proc = subprocess.run(["gcc", src_path, "-o", bin_path], capture_output=True, text=True, timeout=10)
            print(json.dumps({"debug_compile_returncode": compile_proc.returncode, "compile_stdout": compile_proc.stdout, "compile_stderr": compile_proc.stderr}))
            if compile_proc.returncode == 0 and os.path.exists(bin_path):
                for test in tests.get("tests", []):
                    tid = test.get("id")
                    inp = test.get("input", "")
                    try:
                        proc = subprocess.run([bin_path], input=inp, capture_output=True, text=True, timeout=5)
                        print(json.dumps({"test_id": tid, "exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}))
                    except Exception as e:
                        print(json.dumps({"test_id": tid, "exception": str(e)}))
            try:
                os.unlink(src_path)
            except Exception:
                pass
            try:
                if os.path.exists(bin_path):
                    os.unlink(bin_path)
            except Exception:
                pass
        except Exception as e:
            print(json.dumps({"debug_error": str(e)}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
