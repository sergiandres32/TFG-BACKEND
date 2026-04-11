"""
Módulo: runner.py
Propósito:
  Proporciona utilidades para ejecutar binarios de forma controlada y recoger
  su salida (stdout/stderr), código de salida, si expiró por timeout y tiempo de ejecución.

Este módulo expone `run_executable(exec_path, input_data, timeout=5, workdir=None)`
que devuelve un diccionario con los campos mostrados abajo.

Notas:
  - Actualmente la ejecución se realiza con `subprocess.run` y `timeout`.
  - En fases posteriores se añadirá aislamiento (Docker) y límites de recursos.
"""

import os
import subprocess
import time
from typing import Any, Dict, Optional


# Descripción de imports:
# - os: comprobar existencia del ejecutable y manejar rutas
# - subprocess: ejecutar el proceso y capturar saída
# - time: medir tiempo de ejecución
# - typing: anotaciones de tipos


def run_executable(exec_path: str, input_data: str, timeout: int = 5, workdir: Optional[str] = None) -> Dict[str, Any]:
    """Ejecuta el binario `exec_path` pasando `input_data` por stdin.

    Parámetros:
    - exec_path: ruta al ejecutable a ejecutar
    - input_data: cadena que se enviará a stdin del proceso
    - timeout: segundos máximos de ejecución antes de forzar un timeout
    - workdir: directorio de trabajo para la ejecución (opcional)

    Retorna un diccionario con las claves:
      {
        'stdout': str,
        'stderr': str,
        'exit_code': int,
        'timed_out': bool,
        'time': float (segundos)
      }

    Esta función normaliza la salida para que `src/judge.py` pueda consumirla.
    """

    if not os.path.exists(exec_path):
        return {"stdout": "", "stderr": f"Executable not found: {exec_path}", "exit_code": -1, "timed_out": False, "time": 0.0}

    start = time.time()
    try:
        proc = subprocess.run([exec_path], input=input_data, capture_output=True, text=True, timeout=timeout, cwd=workdir)
        elapsed = time.time() - start
        return {"stdout": proc.stdout, "stderr": proc.stderr, "exit_code": proc.returncode, "timed_out": False, "time": elapsed}
    except subprocess.TimeoutExpired as e:
        elapsed = time.time() - start
        # Texto parcial si está disponible
        out = e.stdout or ""
        err = e.stderr or ""
        return {"stdout": out, "stderr": err + "\nProcess timed out", "exit_code": -1, "timed_out": True, "time": elapsed}
    except Exception as e:
        elapsed = time.time() - start
        return {"stdout": "", "stderr": str(e), "exit_code": -1, "timed_out": False, "time": elapsed}


__all__ = ["run_executable"]
"""
Módulo: runner.py
Propósito:
  Contendrá funciones para ejecutar un binario con un input dado, capturar stdout, stderr y código de salida.
  En esta fase inicial solo se describe el propósito del módulo y las funciones que deberá exportar.

Funciones propuestas (a implementar en fases posteriores):
  - run_executable(exec_path: str, input_data: str, timeout: int = 5) -> Dict
      Ejecuta el ejecutable en exec_path, le pasa input_data por stdin y devuelve un diccionario con las claves:
      {
        'stdout': str,
        'stderr': str,
        'exit_code': int,
        'timed_out': bool
      }

Notas para la memoria del TFG:
  - Más adelante este módulo deberá soportar ejecución en contenedores y límites estrictos de CPU/memoria.
  - Es importante sanitizar las entradas y no ejecutar binarios no confiables sin aislamiento (usar Docker luego).
"""

# ...este fichero queda como plantilla para implementar en fases posteriores...
