# Jutge API - Documentación Completa

FastAPI + SQLAlchemy para:
- Registrar/login usuarios (JWT)
- Gestionar asignaturas e inscripciones por usuario
- Consultar ejercicios y test cases públicos
- Enviar submissions de código
- Ver estadísticas personales y leaderboard
- Gestión de jobs asincrónico

## Actualizacion 2026-07-03 - Scope por asignatura

La API ahora filtra contenido academico por asignatura inscrita.

- Nuevo endpoint: `GET /subjects/me` (asignaturas del usuario autenticado)
- Endpoints con soporte de `subject_id` por query:
  - `GET /topics?subject_id=...`
  - `GET /exercises?subject_id=...`
  - `GET /quiz-questions?subject_id=...`
  - `GET /me/progress?subject_id=...`
  - `GET /me/submissions?subject_id=...`
- `POST /topics` requiere `subject_id` en payload.
- `POST /exercises` requiere `topic_id` para mantener scope de asignatura.

Si el usuario no esta inscrito en la asignatura consultada, la API responde `403`.

---

## Setup

### Docker + Postgres (Recomendado)

```bash
# Levanta stack (API, Worker, Database)
make stack-up

# Inicializa DB con datos de prueba
make db-reset-seed

# API disponible en
http://localhost:8000
http://localhost:8000/docs  # Swagger interactivo
```

**Acceso Postgres:**
- Host: `localhost:5432`
- User: `jutge`
- Password: `jutge_pass`
- Database: `jutge_db`

---

## Autenticación

Todos los endpoints (excepto `/users`, `/token`) requieren JWT en el header:

```bash
Authorization: Bearer <token>
```

**Token válido por:** 24 horas

### Roles y RBAC

La API usa control de acceso por rol con dependencias FastAPI.

- **Cualquier usuario autenticado** puede consultar ejercicios, responder quiz, enviar submissions y consultar su progreso.
- **Solo `teacher`** puede crear, editar o borrar contenido académico.

Endpoints protegidos para profesor:

- `GET /students`
- `GET /topics/{id}/students-status`
- `POST /topics`
- `PUT /topics/{id}`
- `DELETE /topics/{id}`
- `POST /exercises`
- `PUT /exercises/{id}`
- `DELETE /exercises/{id}`
- `POST /test_cases`
- `POST /quiz-questions`
- `PUT /quiz-questions/{id}`
- `DELETE /quiz-questions/{id}`

Si un alumno intenta acceder a cualquiera de esos endpoints, la API responde:

```json
{
  "detail": "Only teachers can perform this action"
}
```

con status `403 Forbidden`.

---

## Endpoints de Autenticación

### 1. POST `/users` - Registrar usuario

**Request:**
```json
{
  "username": "alumno_nuevo",
  "email": "alumno@example.com",
  "password": "pass123"
}
```

**Response (200):**
```json
{
  "id": 5,
  "username": "alumno_nuevo",
  "email": "alumno@example.com",
  "role": "student"
}
```

**Errores:**
- `400` - Username o email ya registrado

---

### 2. POST `/token` - Login (Obtener JWT)

**Request:**
```
Content-Type: application/x-www-form-urlencoded

username=alumno_a_base&password=alumno123
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Errores:**
- `400` - Credenciales incorrectas

---

## Endpoints de Asignaturas

Estos endpoints cubren creacion, catalogo, inscripcion de alumnado y gestion docente de asignaturas.

### GET `/subjects/me` - Asignaturas del usuario autenticado

**Headers:**
```
Authorization: Bearer <token>
```

**Response (200):**
```json
[
  {
    "id": 1,
    "code": "PACO",
    "name": "Programacion y Comunicacion",
    "is_active": true,
    "requires_password": false
  }
]
```

### GET `/subjects/catalog` - Catalogo para alumnado

Lista asignaturas activas con flags de estado para el usuario autenticado.

**Response (200):**
```json
[
  {
    "id": 1,
    "code": "PACO",
    "name": "Programacion y Comunicacion",
    "is_active": true,
    "is_enrolled": true,
    "is_assigned": false,
    "requires_password": false
  },
  {
    "id": 2,
    "code": "ADSO",
    "name": "Administracion de Sistemas",
    "is_active": true,
    "is_enrolled": false,
    "is_assigned": false,
    "requires_password": true
  }
]
```

### POST `/subjects/{id}/enroll` - Inscripcion de alumno

**Role requerida:** `student`

**Request:**
```json
{
  "password": "clave_opcional"
}
```

**Response (200):**
```json
{
  "ok": true,
  "message": "Inscripcio completada"
}
```

**Errores:**
- `404` - Asignatura no encontrada
- `400` - Password requerida o password invalida

### POST `/subjects` - Crear asignatura (PROFESOR)

**Role requerida:** `teacher`

Al crear, el profesor queda asignado automaticamente a la nueva asignatura.

**Request:**
```json
{
  "code": "SOD",
  "name": "Sistemas Operativos Distribuidos",
  "enrollment_password": "opcional"
}
```

### GET `/subjects/manage` - Catalogo para gestion docente

**Role requerida:** `teacher`

Incluye asignaturas activas e inactivas, y el estado `is_assigned` para el profesor autenticado.

### POST `/subjects/{id}/assign-self` - Autoasignarse como profesor

**Role requerida:** `teacher`

### DELETE `/subjects/{id}/assign-self` - Desasignarse como profesor

**Role requerida:** `teacher`

### PUT `/subjects/{id}/active` - Activar/desactivar asignatura

**Role requerida:** `teacher` asignado en la asignatura.

### PUT `/subjects/{id}/password` - Configurar password de inscripcion

**Role requerida:** `teacher` asignado en la asignatura.

Request esperado:
- `requires_password=true` requiere `enrollment_password` no vacia.
- `requires_password=false` elimina proteccion de password.

---

## Endpoints de Ejercicios

### 3. GET `/exercises` - Listar todos los ejercicios

**Headers:**
```
Authorization: Bearer <token>
```

**Response (200):**
```json
[
  {
    "id": 1,
    "title": "sum",
    "description": "Sum two integers",
    "level": "beginner",
    "completed": true
  },
  {
    "id": 2,
    "title": "sort_words",
    "description": "Sort words alphabetically",
    "level": "mid",
    "completed": false
  }
]
```

---

### 4. GET `/exercises/{id}` - Obtener ejercicio con test cases públicos

**Request:**
```
GET /exercises/1
Authorization: Bearer <token>
```

**Response (200):**
```json
{
  "id": 1,
  "title": "sum",
  "description": "Sum two integers",
  "level": "beginner",
  "completed": true,
  "public_test_cases": [
    {
      "id": 1,
      "name": "sum_1",
      "content": {
        "input": "2 3\n",
        "expected": "5\n",
        "mode": "exact"
      }
    },
    {
      "id": 2,
      "name": "sum_2",
      "content": {
        "input": "10 20\n",
        "expected": "30\n",
        "mode": "exact"
      }
    }
  ]
}
```

**Errores:**
- `404` - Ejercicio no encontrado
- `401` - Sin autenticación

---

### 5. POST `/exercises` - Crear ejercicio (PROFESOR)

**Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request:**
```json
{
  "title": "Fibonacci",
  "description": "Calculate nth Fibonacci number",
  "level": "expert"
}
```

**Response (200):**
```json
{
  "id": 3,
  "title": "Fibonacci"
}
```

---

### 6. POST `/test_cases` - Crear test case (PROFESOR)

**Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request:**
```json
{
  "exercise_id": 1,
  "name": "test_hidden_1",
  "content": {
    "input": "100 200\n",
    "expected": "300\n",
    "mode": "exact"
  }
}
```

**Response (200):**
```json
{
  "id": 5,
  "name": "test_hidden_1"
}
```

---

## Endpoints de Submissions y Jobs

### 7. POST `/submissions` - Enviar código para evaluar

Crea un **Job** asincrónico que será evaluado por el worker.

**Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request:**
```json
{
  "exercise_id": 1,
  "code": "#include <stdio.h>\nint main() {\n  int a, b;\n  scanf(\"%d %d\", &a, &b);\n  printf(\"%d\\n\", a + b);\n  return 0;\n}\n"
}
```

**Response (200):**
```json
{
  "job_id": 5,
  "status": "pending",
  "message": "Submission queued for evaluation"
}
```

**Errores:**
- `400` - Código vacío o exercise_id inválido
- `404` - Ejercicio no encontrado

**Nota:** El cliente debe hacer polling a `GET /jobs/{job_id}` para obtener resultados

---

### 8. GET `/jobs/{id}` - Obtener estado y resultado de un job

**Headers:**
```
Authorization: Bearer <token>
```

**Request:**
```
GET /jobs/1
```

**Response (200) - Job pendiente:**
```json
{
  "id": 1,
  "user_id": 3,
  "exercise_id": 1,
  "status": "pending",
  "run_id": null,
  "verdict": null,
  "passed_all": null,
  "duration_ms": null,
  "memory_kb": null,
  "details": null,
  "error_message": null,
  "created_at": "2026-03-12T15:30:45.123456",
  "completed_at": null
}
```

**Response (200) - Job completado (AC):**
```json
{
  "id": 1,
  "user_id": 3,
  "exercise_id": 1,
  "status": "completed",
  "run_id": 1,
  "verdict": "AC",
  "passed_all": true,
  "duration_ms": 45,
  "memory_kb": 512,
  "details": {
    "results": [
      {
        "test_id": "sum_1",
        "passed": true,
        "details": "Exact match"
      },
      {
        "test_id": "sum_2",
        "passed": true,
        "details": "Exact match"
      }
    ]
  },
  "error_message": null,
  "created_at": "2026-03-12T15:30:45.123456",
  "completed_at": "2026-03-12T15:30:47.234567"
}
```

**Response (200) - Job completado (WA):**
```json
{
  "id": 4,
  "user_id": 4,
  "exercise_id": 2,
  "status": "completed",
  "run_id": 4,
  "verdict": "WA",
  "passed_all": false,
  "duration_ms": 38,
  "memory_kb": 524,
  "details": {
    "results": [
      {
        "test_id": "sort_1",
        "passed": true,
        "details": "Exact match"
      },
      {
        "test_id": "sort_2",
        "passed": false,
        "details": "Output mismatch"
      }
    ]
  },
  "error_message": null,
  "created_at": "2026-03-12T15:35:10.654321",
  "completed_at": "2026-03-12T15:35:12.765432"
}
```

**Posibles verdicts:** `AC` (Accepted), `WA` (Wrong Answer), `TLE` (Time Limit Exceeded), `CE` (Compilation Error), `RTE` (Runtime Error), `OOM` (Out of Memory)

**Errores:**
- `404` - Job no encontrado
- `403` - No autorizado (job pertenece a otro usuario)

---

## Endpoints de Usuario Autenticado

### 9. GET `/me` - Obtener perfil actual con ranking

**Headers:**
```
Authorization: Bearer <token>
```

**Response (200):**
```json
{
  "id": 3,
  "username": "alumno_a_base",
  "email": "alumno_a_base@example.com",
  "role": "student",
  "leaderboard_rank": 1,
  "completed_exercises": 2
}
```

---

### 10. GET `/me/progress` - Estadísticas de progreso

**Headers:**
```
Authorization: Bearer <token>
```

**Response (200):**
```json
{
  "completed_exercises_count": 2,
  "total_exercises": 2,
  "total_attempts": 2,
  "completion_rate": 1.0,
  "completed_exercises": [
    {
      "exercise_id": 1,
      "exercise_title": "sum",
      "completed_at": "2026-03-12T15:30:47.234567",
      "attempts_needed": 1
    },
    {
      "exercise_id": 2,
      "exercise_title": "sort_words",
      "completed_at": "2026-03-12T15:35:12.765432",
      "attempts_needed": 1
    }
  ]
}
```

---

### 11. GET `/me/submissions` - Historial de submissions del usuario

**Headers:**
```
Authorization: Bearer <token>
```

**Response (200):**
```json
[
  {
    "job_id": 2,
    "exercise_id": 2,
    "exercise_title": "sort_words",
    "status": "completed",
    "verdict": "AC",
    "passed_all": true,
    "created_at": "2026-03-12T15:35:10.654321",
    "completed_at": "2026-03-12T15:35:12.765432"
  },
  {
    "job_id": 1,
    "exercise_id": 1,
    "exercise_title": "sum",
    "status": "completed",
    "verdict": "AC",
    "passed_all": true,
    "created_at": "2026-03-12T15:30:45.123456",
    "completed_at": "2026-03-12T15:30:47.234567"
  }
]
```

---

## Endpoints Públicos

### 12. GET `/leaderboard` - Ver ranking global

**Response (200):**
```json
[
  {
    "user_id": 3,
    "username": "alumno_a_base",
    "completed_count": 2,
    "last_completed_at": "2026-03-12T15:35:12.765432"
  },
  {
    "user_id": 4,
    "username": "alumno_b_base",
    "completed_count": 1,
    "last_completed_at": "2026-03-12T15:30:47.234567"
  },
  {
    "user_id": 1,
    "username": "profesor_seed",
    "completed_count": 0,
    "last_completed_at": null
  }
]
```

---

## Flujo de Uso Típico para Game Client

### Juego quiere registrar un jugador:

```bash
# 1. Registrar
curl -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{
    "username": "jugador_nuevo",
    "email": "jugador@game.com",
    "password": "secret_game_pass"
  }'

# 2. Login
curl -X POST http://localhost:8000/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=jugador_nuevo&password=secret_game_pass"
# Guardar token
```

### Juego quiere que el jugador explore ejercicios:

```bash
TOKEN="<token_del_jugador>"

# 1. Listar todos
curl http://localhost:8000/exercises \
  -H "Authorization: Bearer $TOKEN"

# 2. Ver detalles + test cases públicos
curl http://localhost:8000/exercises/1 \
  -H "Authorization: Bearer $TOKEN"

# 3. Ver progreso personal
curl http://localhost:8000/me/progress \
  -H "Authorization: Bearer $TOKEN"

# 4. Ver posición en leaderboard
curl http://localhost:8000/me \
  -H "Authorization: Bearer $TOKEN"
```

### Juego quiere que el jugador envíe código:

```bash
# 1. Enviar submission
curl -X POST http://localhost:8000/submissions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "exercise_id": 1,
    "code": "#include <stdio.h>\nint main() {\n  int a, b;\n  scanf(\"%d %d\", &a, &b);\n  printf(\"%d\\n\", a + b);\n  return 0;\n}\n"
  }'
# Recibe job_id = 5

# 2. Polling para obtener resultado (repetir hasta que status != pending)
curl http://localhost:8000/jobs/5 \
  -H "Authorization: Bearer $TOKEN"

# Si verdict == "AC" → Éxito! 
# Si verdict == "WA" → Fallo, mostrar detalles en details.results
# Si status == "pending" → Seguir esperando...
```

---

## Configuración y Rendimiento

| Parámetro | Valor |
|-----------|-------|
| Timeout de ejecución | 5 segundos |
| Memoria máxima | 256 MB |
| JWT válido por | 24 horas |
| Max usuarios | Sin límite (DB) |
| Max ejercicios | Sin límite (DB) |
| Job polling timeout | Según cliente |

---

## Errores Comunes

| Error | Causa | Solución |
|-------|-------|----------|
| `401 Unauthorized` | Token inválido/expirado | Re-login, obtener nuevo token |
| `403 Forbidden` | Acceso denegado | Verificar permisos del usuario |
| `404 Not Found` | Recurso no existe | Verificar ID del recurso |
| `400 Bad Request` | Datos inválidos | Revisar payload del request |
| `500 Internal Server Error` | Error en servidor | Revisar logs del API |

---

## TestData Base Disponible

Al ejecutar `make db-reset-seed`:

| Usuario | Email | Password | Completados | Rank |
|---------|-------|----------|-------------|------|
| profesor_seed | profesor_seed@jutge.local | profesor123 | 0 | 3º |
| alumno_a_base | alumno_a_base@example.com | alumno123 | 2 | 1º 🏆 |
| alumno_b_base | alumno_b_base@example.com | alumno123 | 1 | 2º |

Ejercicios seed:
- `sum` (beginner) - 2 test cases públicos
- `sort_words` (mid) - 3 test cases públicos

---

## Desarrollo y Testing

```bash
# Ver logs en tiempo real
make stack-logs

# Ejecutar test E2E
make api-test-base-flow

# Acceder a Swagger interactivo
http://localhost:8000/docs
```
