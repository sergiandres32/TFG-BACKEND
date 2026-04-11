# Guía Rápida

## Estructura

```
jutge/
├── src/
│   ├── judge.py
│   ├── compiler.py
│   ├── runner.py
│   └── evaluator.py
├── test_cases/
│   └── sort_words/
│       └── tests.json           (definición de pruebas)
├── submissions/
│   └── estudiante1_sort_words.c (programa a evaluar)
└── README.md
```

## Comando

```bash
python3 src/judge.py <archivo_c> <archivo_pruebas.json> [--timeout N] [--debug]
```

Parámetros:
- `<archivo_c>`: ruta al programa C del estudiante
- `<archivo_pruebas.json>`: ruta al archivo JSON con las pruebas
- `--timeout N`: tiempo máximo de ejecución por prueba en segundos (por defecto: 5)
- `--debug`: muestra información adicional durante la ejecución

Ejemplo:
```bash
python3 src/judge.py submissions/estudiante1_sort_words.c test_cases/sort_words/tests.json
```

## Salida

```json
{
  "results": [
    {"test": "simple", "passed": true, "details": "Exact match"},
    {"test": "inverso", "passed": true, "details": "Exact match"}
  ],
  "summary": {"passed": 3, "failed": 0}
}
```

## Crear una suite de pruebas

1. Crear carpeta: `test_cases/nombre_ejercicio/`
2. Crear archivo: `tests.json` (definición de pruebas)

## Enviar solución de estudiante

1. Guardar archivo en: `submissions/`
2. Nombrar con patrón: `estudiante_nombre_ejercicio.c`
3. Ejecutar: `python3 src/judge.py submissions/estudiante_nombre_ejercicio.c test_cases/nombre_ejercicio/tests.json`

### Estructura de tests.json

```json
{
  "name": "Descripción del ejercicio",
  "tests": [
    {
      "id": "test_1",
      "input": "3\na\nb\nc\n",
      "mode": "exact",
      "expected": "a\nb\nc\n",
      "ignore_whitespace": false
    }
  ]
}
```

Campos:
- `id`: identificador único de la prueba
- `input`: entrada que se pasa al programa por stdin
- `mode`: tipo de evaluación (exact | lines | regex)
- `expected`: salida esperada
- `ignore_whitespace`: si true, tolera diferencias en espacios en blanco

## Modos de evaluación

| Modo | Descripción |
|---|---|
| `exact` | Comparación exacta de salida (incluyendo espacios y saltos de línea) |
| `lines` | Comparación línea por línea |
| `regex` | Búsqueda de patrones con expresiones regulares |

Documentación completa en USAGE_GUIDE.md
