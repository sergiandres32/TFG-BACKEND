"""
Módulo: schema_validator.py
Propósito:
  Validar archivos JSON de test_cases contra un esquema predefinido.
  Proporciona errores claros si la estructura es incorrecta.
"""

import json
from typing import Tuple, Dict, Any


# Esquema de validación para test_cases
TEST_CASES_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "tests": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "input": {"type": "string"},
                    "mode": {"enum": ["exact", "lines", "regex"]},
                    "expected": {"type": "string"},
                    "ignore_whitespace": {"type": "boolean"},
                    "description": {"type": "string"}
                },
                "required": ["id", "input", "mode", "expected"]
            },
            "minItems": 1
        }
    },
    "required": ["tests"]
}


def _validate_required_fields(obj: Dict, required: list, path: str) -> list:
    """Verifica que los campos requeridos existan."""
    errors = []
    for field in required:
        if field not in obj:
            errors.append(f"Campo requerido '{field}' falta en {path}")
    return errors


def _validate_field_type(value: Any, expected_type: str, field_name: str, path: str) -> list:
    """Verifica que un campo tenga el tipo correcto."""
    errors = []
    type_map = {
        "string": str,
        "boolean": bool,
        "number": (int, float),
        "array": list,
        "object": dict
    }
    
    expected_python_type = type_map.get(expected_type)
    if expected_python_type and not isinstance(value, expected_python_type):
        errors.append(f"Campo '{field_name}' en {path} debe ser {expected_type}, recibió {type(value).__name__}")
    
    return errors


def _validate_enum(value: str, allowed: list, field_name: str, path: str) -> list:
    """Verifica que un valor esté en una lista permitida."""
    errors = []
    if value not in allowed:
        errors.append(f"Campo '{field_name}' en {path} debe ser uno de {allowed}, recibió '{value}'")
    return errors


def validate_test_cases(json_path: str) -> Tuple[bool, str]:
    """Valida un archivo JSON de test_cases contra el esquema.
    
    Retorna:
        (valid: bool, message: str)
        - Si válido: (True, "JSON válido")
        - Si inválido: (False, "Descripción de errores")
    """
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        return False, f"Archivo no encontrado: {json_path}"
    except json.JSONDecodeError as e:
        return False, f"JSON inválido: {e}"
    except Exception as e:
        return False, f"Error al leer archivo: {e}"
    
    errors = []
    
    # Verificar que es un objeto
    if not isinstance(data, dict):
        return False, "El archivo debe contener un objeto JSON, no una lista"
    
    # Verificar campos requeridos en raíz
    errors.extend(_validate_required_fields(data, ["tests"], "raíz"))
    
    if "tests" not in data:
        return False, "\n".join(errors) if errors else "Campo 'tests' requerido"
    
    # Verificar que tests es un array
    if not isinstance(data["tests"], list):
        errors.append("Campo 'tests' debe ser un array")
        return False, "\n".join(errors)
    
    # Verificar que hay al menos una prueba
    if len(data["tests"]) == 0:
        errors.append("Array 'tests' debe contener al menos una prueba")
        return False, "\n".join(errors)
    
    # Validar cada test
    for idx, test in enumerate(data["tests"]):
        test_path = f"tests[{idx}]"
        
        if not isinstance(test, dict):
            errors.append(f"{test_path} debe ser un objeto")
            continue
        
        # Campos requeridos
        errors.extend(_validate_required_fields(test, ["id", "input", "mode", "expected"], test_path))
        
        # Tipos
        if "id" in test and not isinstance(test["id"], str):
            errors.append(f"Campo 'id' en {test_path} debe ser string")
        if "input" in test and not isinstance(test["input"], str):
            errors.append(f"Campo 'input' en {test_path} debe ser string")
        if "expected" in test and not isinstance(test["expected"], str):
            errors.append(f"Campo 'expected' en {test_path} debe ser string")
        
        # Mode debe ser válido
        if "mode" in test:
            errors.extend(_validate_enum(test["mode"], ["exact", "lines", "regex"], "mode", test_path))
        
        # ignore_whitespace debe ser boolean (si existe)
        if "ignore_whitespace" in test and not isinstance(test["ignore_whitespace"], bool):
            errors.append(f"Campo 'ignore_whitespace' en {test_path} debe ser boolean (true/false)")
    
    if errors:
        return False, "\n".join(errors)
    
    return True, "JSON válido"


__all__ = ["validate_test_cases", "TEST_CASES_SCHEMA"]
