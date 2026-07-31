# 🚀 Integración Judge + API: Guía completa

## Novedad 2026-07-03: Integracion por asignatura

Antes de listar temas/ejercicios, el cliente debe consultar las asignaturas del usuario:

1. `GET /subjects/me`
2. Elegir `subject_id` activo en UI
3. Consumir contenido filtrado:
  - `GET /topics?subject_id=...`
  - `GET /exercises?subject_id=...`
  - `GET /quiz-questions?subject_id=...`
  - `GET /me/progress?subject_id=...`
  - `GET /me/submissions?subject_id=...`

Si se consulta una asignatura no inscrita, la API retorna `403`.

### Flujo de descubrimiento e inscripcion (alumnado)

```mermaid
flowchart TD
  A[Login student] --> B[GET /subjects/catalog]
  B --> C{Asignatura requiere password?}
  C -- No --> D[POST /subjects/{id}/enroll]
  C -- Si --> E[Alumno introduce password]
  E --> D
  D --> F[GET /subjects/me]
  F --> G[Seleccionar subject_id activo]
  G --> H[Consumir topics/exercises/progress por subject_id]
```

Respuestas utiles de `POST /subjects/{id}/enroll`:
- Inscripcion nueva: `{"ok": true, "message": "Inscripcio completada"}`
- Ya inscrito: `{"ok": true, "message": "Already enrolled"}`

## Novedad 2026-07-24: Launch LTI 1.1 (Atenea)

Jutge incorpora endpoint de launch LTI para integracion con Moodle/Atenea.

Flujo resumido:

1. Profesor configura plataforma LTI (`POST /lti/platforms`) con `consumer_key` y `consumer_secret`.
2. Atenea envia POST firmado a `POST /lti/launch`.
3. Jutge valida OAuth 1.0 (`HMAC-SHA1`).
4. Jutge mapea `user_id` LMS a usuario interno (auto-crea si no existe).
5. Jutge mapea `context_id` a asignatura interna:
  - Instructor: puede auto-crear asignatura/contexto si no existe mapeo.
  - Student: requiere mapeo ya existente.
6. Jutge devuelve JWT interno para consumir API normal.

Claims LTI usados actualmente:
- `oauth_consumer_key`
- `user_id`
- `roles`
- `context_id`
- `context_title`
- `resource_link_id`
- `lis_person_contact_email_primary` (opcional)
- `lis_person_name_full` / `ext_user_username`

## 📊 Códigos de Error Explicados

| Código | Significado | Ejemplo |
|--------|-----------|---------|
| **AC** | Accepted - Todos tests pasaron | ✅ |
| **WA** | Wrong Answer - Output incorrecto | Espera `3` pero devuelve `6` (multiplicó en lugar de sumar) |
| **CE** | Compile Error - No compila | Error de sintaxis, imports faltantes |
| **TLE** | Time Limit Exceeded - Tardó > timeout | Bucle infinito, algoritmo O(n²) muy lento |
| **RTE** | Runtime Error - Crash durante ejecución | SIGSEGV (puntero nulo), división por cero |
| **OOM** | Out of Memory - Agotó memoria | Alocó 10GB en un sistema limitado a 256MB |

## 🔄 Flujo completo: Usuario → API → Judge → DB

```
1. Usuario sube código C
   POST /submissions
   {
     "exercise_id": 1,
     "code": "#include <stdio.h>\nint main() { ... }"
   }

2. API llama a judge_v2.run_and_evaluate_all_tests()
   ├─ Compilar código (gcc)
   │  ├─ Éxito → vinculación y ejecución
   │  └─ Error → CE (compile_error guardado)
   │
   ├─ Para cada test:
   │  ├─ Ejecutar binario con input
   │  ├─ Capturar stdout/stderr/exit_code/time
   │  ├─ Detectar:
   │  │  ├─ Timeout → TLE
   │  │  ├─ OOMKiller (exit 137 en Docker) → OOM
   │  │  ├─ Exit != 0 (no timeout) → RTE
   │  │  └─ Comparar output con expected → AC/WA
   │  └─ Acumular resultados
   │
   └─ Determinar verdict final:
      AC: todos pasaron
      TLE/OOM/RTE/CE: si hay alguno de estos
      WA: si ninguno de arriba pero no todo pasó

3. API guarda Run en DB
   {
     "user_id": 1,
     "exercise_id": 1,
     "verdict": "AC",
     "passed": true,
     "details": {
       "results": [
         {"test_id": "t1", "passed": true, "details": "Exact match"},
         {"test_id": "t2", "passed": true, "details": "Exact match"}
       ],
       "compile_error": null
     },
     "duration_ms": 45
   }

4. Si verdict == AC y no existe completion:
   ├─ Crear UserExerciseCompletion
   ├─ Usuario progresa en ranking
   └─ Sistema registra progreso

5. Respuesta API:
   {
     "run_id": 42,
     "verdict": "AC",
     "passed": true,
     "details": { ... }
   }
```

## 📝 Ejemplos de Uso

### 1️⃣ Registrar usuario

```bash
curl -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{
    "username": "alice",
    "email": "alice@example.com",
    "password": "pass123"
  }'
```

Respuesta:
```json
{
  "id": 1,
  "username": "alice",
  "email": "alice@example.com",
  "role": "student"
}
```

### 2️⃣ Login

```bash
curl -X POST http://localhost:8000/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=alice&password=pass123"
```

Respuesta:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

Guarda el token: `TOKEN="eyJ0eXAiOiJKV1QiLCJhbGc..."`

### 3️⃣ Crear ejercicio (Sum)

```bash
TOKEN="eyJ0eXAiOiJKV1QiLCJhbGc..."

curl -X POST http://localhost:8000/exercises \
  -H "Authorization: bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Sum Two Numbers",
    "level": "beginner",
    "description": "Add two integers from stdin and print result"
  }'
```

Respuesta:
```json
{
  "id": 1,
  "title": "Sum Two Numbers"
}
```

### 4️⃣ Crear test cases para el ejercicio

```bash
curl -X POST http://localhost:8000/test_cases \
  -H "Authorization: bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "exercise_id": 1,
    "name": "Test 1",
    "content": {
      "input": "1 2\n",
      "expected": "3\n",
      "mode": "exact"
    }
  }'

curl -X POST http://localhost:8000/test_cases \
  -H "Authorization: bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "exercise_id": 1,
    "name": "Test 2",
    "content": {
      "input": "5 5\n",
      "expected": "10\n",
      "mode": "exact"
    }
  }'
```

### 5️⃣ Enviar submission (CODIGO CORRECTO)

```bash
TOKEN="eyJ0eXAiOiJKV1QiLCJhbGc..."

curl -X POST http://localhost:8000/submissions \
  -H "Authorization: bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "exercise_id": 1,
    "code": "#include <stdio.h>\nint main() {\n    int a, b;\n    scanf(\"%d %d\", &a, &b);\n    printf(\"%d\\n\", a + b);\n    return 0;\n}"
  }'
```

Respuesta (AC):
```json
{
  "run_id": 1,
  "verdict": "AC",
  "passed": true,
  "details": {
    "results": [
      {"test_id": "Test 1", "passed": true, "details": "Exact match"},
      {"test_id": "Test 2", "passed": true, "details": "Exact match"}
    ],
    "compile_error": null
  }
}
```

### 6️⃣ Enviar submission (CODIGO INCORRECTO - WA)

```bash
curl -X POST http://localhost:8000/submissions \
  -H "Authorization: bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "exercise_id": 1,
    "code": "#include <stdio.h>\nint main() {\n    int a, b;\n    scanf(\"%d %d\", &a, &b);\n    printf(\"%d\\n\", a * b);\n    return 0;\n}"
  }'
```

Respuesta (WA):
```json
{
  "run_id": 2,
  "verdict": "WA",
  "passed": false,
  "details": {
    "results": [
      {"test_id": "Test 1", "passed": false, "details": "Mismatch"},
      {"test_id": "Test 2", "passed": false, "details": "Mismatch"}
    ],
    "compile_error": null
  }
}
```

### 7️⃣ Enviar submission (CODIGO INVÁLIDO - CE)

```bash
curl -X POST http://localhost:8000/submissions \
  -H "Authorization: bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "exercise_id": 1,
    "code": "#include <stdio.h>\nint main() {\n    printf(\"missing closing paren\"\n    return 0;\n}"
  }'
```

Respuesta (CE):
```json
{
  "run_id": 3,
  "verdict": "CE",
  "passed": false,
  "details": {
    "results": [],
    "compile_error": "/tmp/...: error: expected ')' before 'return'\n..."
  }
}
```

### 8️⃣ Ver leaderboard

```bash
curl http://localhost:8000/leaderboard
```

Respuesta:
```json
[
  {
    "username": "alice",
    "completed_count": 1,
    "last_completed_at": "2026-02-23T10:30:45.123456"
  }
]
```

## 🐳 Ejecutar con Docker

```bash
# Levantar Postgres + API
docker-compose -f docker-compose-api.yml up

# En otra terminal, testear
TOKEN=$(curl -s -X POST http://localhost:8000/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=alice&password=pass123" | jq -r '.access_token')

echo "Token: $TOKEN"

# Ahora usar $TOKEN en requests
curl -H "Authorization: bearer $TOKEN" http://localhost:8000/leaderboard
```

## ⚙️ Detalles técnicos

### judge_v2.py
- Ubicación: `src/judge_v2.py`
- Función principal: `run_and_evaluate_all_tests(source_code, tests_obj, timeout, workdir)`
- Genera `Verdict` enum: AC, WA, CE, TLE, RTE, OOM

### API endpoints que integran judge
- `POST /submissions` → despacha a `crud.evaluate_submission_with_judge()`
- Soporta dos modos:
  - Con `code`: evaluación real (llama a judge_v2)
  - Con `results`: evaluación simulada (testing)

### DB Models
- `Run`: Almacena cada intento (verdict, passed, details, duration_ms, memory_kb)
- `UserExerciseCompletion`: Registra cuando un usuario supera un ejercicio por primera vez
- `TestCase`: Almacena contenido de tests en JSON

## 🔮 Próximos pasos

- [ ] Worker asincrónico en cola (RabbitMQ/Celery) para evaluar en background
- [ ] Timeout global por studiant + limites de recursos (Docker)
- [ ] Pass rules: determinar si usuario ha alcanzado cierto level
- [ ] Webhooks: notificar cuando completa ejercicio/level
- [ ] Analytics: dashboard de progreso por estudiante/curso/ejercicio
