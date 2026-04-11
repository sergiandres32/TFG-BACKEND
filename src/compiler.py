"""
Módulo: compiler.py
Propósito:
  Contendrá funciones para compilar código en C usando herramientas del sistema (por ejemplo, gcc).
  En esta fase inicial solo se describe el propósito del módulo y las funciones que deberá exportar.

Funciones propuestas (a implementar en fases posteriores):
  - compile_source(source_path: str, output_path: str) -> Tuple[bool, str]
      Recibe la ruta del fichero fuente C y la ruta donde colocar el ejecutable.
      Devuelve (success, message) donde message contiene stdout/stderr del compilador o un mensaje de error.

Notas para la memoria del TFG:
  - Este módulo deberá ejecutar procesos externos de forma segura, controlar timeouts y límites de recursos
    (p. ej. utilizando subprocess con preexec_fn en Unix o herramientas como psutil).
  - Más adelante se añadirá una opción para compilar dentro de contenedores Docker para aislar la ejecución.
"""

# ...este fichero queda como plantilla para implementar en fases posteriores...

import os
import shutil
import subprocess
from typing import List, Tuple, Optional


def _find_compiler() -> Optional[str]:
  """Busca un compilador disponible en PATH. Devuelve 'gcc' o 'clang' si están disponibles.

  Si ninguno está presente devuelve None.
  """
  for c in ("gcc", "clang"):
    if shutil.which(c):
      return c
  return None


def compile_source(source_path: str, output_path: str, timeout: int = 20, extra_flags: List[str] = None) -> Tuple[bool, str]:
  """Compila el fichero fuente C en `source_path` produciendo el ejecutable en `output_path`.

  Parámetros:
  - source_path: ruta al fichero .c
  - output_path: ruta deseada para el ejecutable resultante
  - timeout: tiempo máximo en segundos para la compilación
  - extra_flags: lista opcional de flags a pasar al compilador (['-O2', '-std=c11'], ...)

  Retorna (success: bool, message: str) donde `message` contiene stdout+stderr del compilador
  o una descripción del error si no se pudo ejecutar el compilador.
  """

  compiler = _find_compiler()
  if compiler is None:
    return False, "No se encontró gcc ni clang en PATH"

  if extra_flags is None:
    extra_flags = []

  # Asegurar que el directorio destino existe
  out_dir = os.path.dirname(output_path)
  if out_dir and not os.path.exists(out_dir):
    os.makedirs(out_dir, exist_ok=True)

  cmd = [compiler, source_path, "-o", output_path] + extra_flags
  try:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    success = proc.returncode == 0
    message = (proc.stdout or "") + (proc.stderr or "")
    return success, message
  except subprocess.TimeoutExpired:
    return False, f"Compilación excedió el timeout de {timeout} segundos"
  except Exception as e:
    return False, str(e)


__all__ = ["compile_source"]
