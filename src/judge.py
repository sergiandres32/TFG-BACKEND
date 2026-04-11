"""
Script principal: judge.py
Propósito:
  Orquesta el flujo principal del juez automático: compilar, ejecutar y evaluar un programa C contra un conjunto
  de pruebas definidas en un fichero JSON.

En esta fase inicial este fichero solo contendrá comentarios que describen cómo deberá funcionar el script y
las opciones de línea de comandos que debe soportar.

Comportamiento esperado (a implementar en fases posteriores):
  1. Recibir como argumentos:
     - ruta al fichero fuente C
     - ruta al fichero JSON con las pruebas
     - opciones (timeout, directorio de trabajo, modo debug)
  2. Invocar al módulo de compilación para generar un ejecutable en un directorio temporal
  3. Por cada prueba en el JSON:
     - ejecutar el binario con el input de la prueba
     - capturar stdout/stderr y tiempo de ejecución
     - validar la salida usando el módulo evaluator
  4. Mostrar un resumen con resultados por prueba, y un resultado global (aprobado/denegado)

Formato de salida sugerido (por ejemplo):
  {
    "results": [
      {"test": "prueba_1", "passed": true, "details": "Coincide patrón X"},
      ...
    ],
    "summary": {"passed": 3, "failed": 1}
  }

Notas para la memoria del TFG:
  - Documentar los posibles códigos de salida y cómo interpretar errores del compilador o del runtime.
  - Explicar la separación de responsabilidades entre módulos para facilitar la extensión y pruebas unitarias.
"""

# ...este fichero queda como plantilla para implementar en fases posteriores...

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List


# Descripción de imports:
# - argparse: parseo de argumentos de la línea de comandos (source, tests, timeout...)
# - json: lectura/escritura de datos en formato JSON (tests y salida de resultados)
# - os: utilidades de sistema (rutas, comprobaciones)
# - re: evaluación de salidas mediante expresiones regulares
# - shutil: limpieza de directorios temporales
# - subprocess: ejecutar procesos externos (compilador y binario)
# - sys: manejo de la salida del programa y códigos de retorno
# - tempfile: creación de directorios temporales para compilación/ejecución
# - time: medir tiempos de ejecución
# - typing: anotaciones de tipo para mayor claridad


def compile_with_gcc(source_path: str, output_path: str) -> (bool, str):
  """Compila un fichero C usando `gcc`.

  Retorna una tupla (success, message) donde `message` contiene la salida
  del compilador (stdout+stderr) o un mensaje de error si `gcc` no está disponible.
  Esta función actúa como fallback mientras no se implemente `src.compiler.compile_source`.
  """

  # Construye el comando de compilación y lo ejecuta
  cmd = ["gcc", source_path, "-o", output_path]
  try:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    success = proc.returncode == 0
    message = proc.stdout + proc.stderr
    return success, message
  except FileNotFoundError:
    return False, "gcc not found on PATH"


def run_executable(exec_path: str, input_data: str, timeout: int = 5) -> Dict[str, Any]:
  """Ejecuta el binario indicado, pasando `input_data` por stdin.

  Devuelve un diccionario con claves: 'stdout', 'stderr', 'exit_code', 'timed_out', 'time'.
  Controla el `timeout` y normaliza la salida para el orquestador.
  """

  try:
    start = time.time()
    proc = subprocess.run([exec_path], input=input_data, capture_output=True, text=True, timeout=timeout)
    duration = time.time() - start
    return {
      "stdout": proc.stdout,
      "stderr": proc.stderr,
      "exit_code": proc.returncode,
      "timed_out": False,
      "time": duration,
    }
  except subprocess.TimeoutExpired as e:
    return {"stdout": e.stdout or "", "stderr": e.stderr or "", "exit_code": -1, "timed_out": True, "time": timeout}


def _normalize_text(s: str, ignore_whitespace: bool) -> str:
  """Normaliza texto para comparación."""
  if ignore_whitespace:
    return " ".join(s.split())
  return s


def evaluate_output(actual: str, test: Dict[str, Any]) -> Dict[str, Any]:
  """Evalúa la salida `actual` frente a la especificación de `test`.

  Devuelve un dict con `passed` y `details`.
  Soporta modos: 'regex' (defecto), 'exact', 'lines'.
  
  IMPORTANTE: No se realiza stripped automático. La salida debe coincidir exactamente
  incluyendo saltos de línea. Es responsabilidad del estudiante producir la salida correcta.
  """

  mode = test.get("mode", "regex")
  ignore_ws = bool(test.get("ignore_whitespace", False))

  if mode == "regex":
    pattern = test.get("expected_pattern") or test.get("expected")
    if not pattern:
      return {"passed": False, "details": "No pattern provided for regex mode"}
    try:
      m = re.search(pattern, actual, flags=re.MULTILINE)
      if m:
        return {"passed": True, "details": "Pattern matched"}
      else:
        return {"passed": False, "details": "Pattern did not match"}
    except re.error as e:
      return {"passed": False, "details": f"Invalid regex: {e}"}

  if mode == "exact":
    expected = test.get("expected")
    if expected is None:
      return {"passed": False, "details": "No expected text for exact mode"}
    # Comparación exacta: sin stripped automático
    out_n = _normalize_text(actual, ignore_ws)
    exp_n = _normalize_text(expected, ignore_ws)
    if out_n == exp_n:
      return {"passed": True, "details": "Exact match"}
    else:
      return {"passed": False, "details": f"Exact mismatch (got {repr(out_n)}, expected {repr(exp_n)})"}

  if mode == "lines":
    expected = test.get("expected")
    if expected is None:
      return {"passed": False, "details": "No expected text for lines mode"}
    out_lines = [_normalize_text(l, ignore_ws) for l in actual.splitlines()]
    exp_lines = [_normalize_text(l, ignore_ws) for l in expected.splitlines()]
    if out_lines == exp_lines:
      return {"passed": True, "details": "Lines match"}
    else:
      return {"passed": False, "details": f"Lines differ (got {len(out_lines)} lines, expected {len(exp_lines)} lines)"}

  return {"passed": False, "details": f"Unknown mode: {mode}"}


def load_tests(json_path: str) -> Dict[str, Any]:
  """Carga y parsea el fichero JSON de pruebas.

  Se espera un objeto JSON con una clave 'tests' que contenga la lista de pruebas.
  """

  with open(json_path, "r", encoding="utf-8") as f:
    return json.load(f)


def main(argv: List[str]) -> int:
  """Punto de entrada del CLI del juez.

  Responsabilidades principales:
  - Parsear argumentos de la línea de comandos.
  - Preparar un directorio de trabajo temporal.
  - Compilar la fuente (usando `src.compiler` si existe, sino `gcc`).
  - Ejecutar cada prueba y evaluar la salida.
  - Imprimir un JSON con `results` y `summary`.
  """

  parser = argparse.ArgumentParser(description="Juez automático (CLI mínimo)")
  parser.add_argument("source", help="Ruta al fichero fuente C")
  parser.add_argument("tests", help="Ruta al fichero JSON con las pruebas")
  parser.add_argument("--timeout", type=int, default=5, help="Timeout por prueba (s)")
  parser.add_argument("--workdir", default=None, help="Directorio de trabajo (por defecto temporal)")
  parser.add_argument("--debug", action="store_true", help="Modo debug: muestra información adicional")

  args = parser.parse_args(argv)

  workdir = args.workdir or tempfile.mkdtemp(prefix="tfg_judge_")
  if args.debug:
    print(f"Using workdir: {workdir}")

  try:
    tests_obj = load_tests(args.tests)
  except Exception as e:
    print(json.dumps({"error": f"Failed to load tests JSON: {e}"}, ensure_ascii=False))
    return 2

  source = args.source
  exe_path = os.path.join(workdir, "submission_exec")

  # Try to use project's compiler module if available
  try:
    from src import compiler as project_compiler  # type: ignore
  except Exception:
    project_compiler = None

  compiled = False
  compile_message = ""
  if project_compiler and hasattr(project_compiler, "compile_source"):
    try:
      success, msg = project_compiler.compile_source(source, exe_path)
      compiled = success
      compile_message = msg
    except Exception as e:
      compiled = False
      compile_message = str(e)
  else:
    compiled, compile_message = compile_with_gcc(source, exe_path)

  if not compiled:
    # Mostrar mensaje de compilación en stderr para facilitar el diagnóstico
    try:
      print(compile_message, file=sys.stderr)
    except Exception:
      pass

    print(json.dumps({"results": [], "summary": {"passed": 0, "failed": 0}, "compile_error": compile_message}, ensure_ascii=False))
    return 1

  results = []
  passed = 0
  failed = 0

  for t in tests_obj.get("tests", []):
    tid = t.get("id") or t.get("name") or "unnamed"
    input_data = t.get("input", "")
    r = run_executable(exe_path, input_data, timeout=args.timeout)

    # Try project evaluator if available
    try:
      from src import evaluator as project_evaluator  # type: ignore
      if hasattr(project_evaluator, "evaluate_output"):
        eval_res = project_evaluator.evaluate_output(r.get("stdout", ""), [t])
        # project evaluator may return list; normalize
        if isinstance(eval_res, list):
          eval_entry = eval_res[0]
        else:
          eval_entry = eval_res
      else:
        eval_entry = evaluate_output(r.get("stdout", ""), t)
    except Exception:
      eval_entry = evaluate_output(r.get("stdout", ""), t)

    entry = {"test": tid, "passed": bool(eval_entry.get("passed")), "details": eval_entry.get("details", ""), "runtime": r}
    results.append(entry)
    if entry["passed"]:
      passed += 1
    else:
      failed += 1

  summary = {"passed": passed, "failed": failed}
  output = {"results": results, "summary": summary}
  print(json.dumps(output, ensure_ascii=False))

  # Cleanup temporary workdir if we created it
  if args.workdir is None:
    try:
      shutil.rmtree(workdir)
    except Exception:
      pass

  return 0


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
