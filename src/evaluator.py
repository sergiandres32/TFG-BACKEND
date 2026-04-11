"""
Módulo: evaluator.py
Propósito:
  Validar la salida de programas frente a pruebas definidas.

API principal:
  - evaluate_output(output: str, tests: List[Dict]) -> List[Dict]

Cada prueba puede contener las claves:
  - id: identificador de la prueba
  - expected_pattern: (para mode 'regex') expresión regular que debe aparecer
  - expected: (para mode 'exact' o 'lines') texto esperado
  - mode: 'regex' (por defecto), 'exact' o 'lines'
  - ignore_whitespace: bool para ignorar espacios en comparaciones (opcional)

La función devuelve una lista de resultados con: { 'id', 'passed', 'details', 'matched_groups' }

En fases posteriores se podrán añadir comparaciones numéricas, tolerancias y extracción
de grupos nombrados.
"""

import re
from typing import Any, Dict, List


# Descripción de imports:
# - re: manejo de expresiones regulares para el modo 'regex'
# - typing: anotaciones de tipos


def _normalize_text(s: str, ignore_whitespace: bool) -> str:
    if ignore_whitespace:
        # Reduce secuencias de whitespace a un solo espacio y strip
        return " ".join(s.split())
    return s


def _eval_regex(output: str, pattern: str) -> Dict[str, Any]:
    try:
        m = re.search(pattern, output, flags=re.MULTILINE)
        if not m:
            return {"passed": False, "details": "Pattern did not match", "matched_groups": None}
        # Return named groups if any
        groups = m.groupdict() if m.groupdict() else m.groups()
        return {"passed": True, "details": "Pattern matched", "matched_groups": groups}
    except re.error as e:
        return {"passed": False, "details": f"Invalid regex: {e}", "matched_groups": None}


def _eval_exact(output: str, expected: str, ignore_whitespace: bool) -> Dict[str, Any]:
    out_n = _normalize_text(output.strip(), ignore_whitespace)
    exp_n = _normalize_text(expected.strip(), ignore_whitespace)
    if out_n == exp_n:
        return {"passed": True, "details": "Exact match"}
    else:
        return {"passed": False, "details": "Exact mismatch"}


def _eval_lines(output: str, expected: str, ignore_whitespace: bool) -> Dict[str, Any]:
    out_lines = [ _normalize_text(l, ignore_whitespace) for l in output.strip().splitlines() ]
    exp_lines = [ _normalize_text(l, ignore_whitespace) for l in expected.strip().splitlines() ]
    if out_lines == exp_lines:
        return {"passed": True, "details": "Lines match"}
    else:
        # Provide simple diff-like detail
        return {"passed": False, "details": f"Lines differ (got {len(out_lines)} lines, expected {len(exp_lines)} lines)"}


def evaluate_output(output: str, tests: List[Dict]) -> List[Dict]:
    """Evalúa `output` frente a una lista de `tests`.

    Para cada test se devuelve un dict con al menos: `id`, `passed` y `details`.
    """
    results: List[Dict] = []
    for t in tests:
        tid = t.get("id") or t.get("name") or "unnamed"
        mode = t.get("mode", "regex")
        ignore_ws = bool(t.get("ignore_whitespace", False))

        if mode == "regex":
            pattern = t.get("expected_pattern") or t.get("expected")
            if not pattern:
                results.append({"id": tid, "passed": False, "details": "No pattern provided for regex mode"})
                continue
            res = _eval_regex(output, pattern)
            res.update({"id": tid})
            results.append(res)
            continue

        if mode == "exact":
            expected = t.get("expected")
            if expected is None:
                results.append({"id": tid, "passed": False, "details": "No expected text for exact mode"})
                continue
            res = _eval_exact(output, expected, ignore_ws)
            res.update({"id": tid})
            results.append(res)
            continue

        if mode == "lines":
            expected = t.get("expected")
            if expected is None:
                results.append({"id": tid, "passed": False, "details": "No expected text for lines mode"})
                continue
            res = _eval_lines(output, expected, ignore_ws)
            res.update({"id": tid})
            results.append(res)
            continue

        results.append({"id": tid, "passed": False, "details": f"Unknown mode: {mode}"})

    return results


__all__ = ["evaluate_output"]
"""
Módulo: evaluator.py
Propósito:
  Contendrá funciones para validar la salida de un programa frente a patrones definidos mediante expresiones regulares.
  En esta fase inicial solo se describe el propósito del módulo y las funciones que deberá exportar.

Funciones propuestas (a implementar en fases posteriores):
  - evaluate_output(output: str, tests: List[Dict]) -> List[Dict]
      Toma la salida completa del programa y una lista de pruebas donde cada prueba define un patrón regex y
      la evaluación esperada. Devuelve una lista con el resultado de cada prueba (pass/fail y detalles).

Notas para la memoria del TFG:
  - Se recomienda permitir patrones con grupos nombrados para extraer información útil (p. ej. puntuaciones).
  - Las comparaciones deben poder configurarse (entera, por líneas, ignorando espacios en blanco, etc.).
"""

# ...este fichero queda como plantilla para implementar en fases posteriores...
