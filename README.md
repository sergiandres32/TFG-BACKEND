# Jutge - Automatic Code Judge

An automated grading system for C programming exercises with strict evaluation, Docker isolation, and real-time async processing.

## Quick Start

```bash
# 1) Levanta API + PostgreSQL + Worker + Streamlit admin + student en background
make stack-up

# 2) En otra terminal: reinicia DB y carga datos seed (profesor, alumnos, topics, ejercicios, test cases)
make db-reset-seed

# 3) API docs (Swagger)
http://localhost:8000/docs

# 4) Panel admin Streamlit (profesor)
http://localhost:8501

# 5) Panel student Streamlit (alumno)
http://localhost:8502

# 6) Suite E2E API completa (Newman en Docker)
make newman-docker-all
```

Resumen rapido de comandos:

- make stack-up: arranca el stack Docker completo (API, PostgreSQL, worker, Streamlit admin, student y subjects).
- make db-reset-seed: limpia y vuelve a sembrar la base de datos para empezar desde estado conocido.
- make newman-docker-all: ejecuta contratos + errores + flujo E2E multi-actor usando colecciones Postman.

## Funcionamiento con Atenea sin deploy

Este flujo permite probar LTI con Atenea desde tu maquina local, sin desplegar en servidor.

1. Levanta el stack local:

```bash
make stack-up
make db-reset-seed
```

2. Expone una URL publica HTTPS con ngrok:

```bash
ngrok http 8080 --region eu
```

Si no usas router/nginx unico, usa dos tuneles:

```bash
ngrok http 8000 --region eu
ngrok http 8502 --region eu
```

3. Configura `.env` con la URL publica de la UI student:

```env
LTI_UI_BASE_URL=https://TU-URL-PUBLICA-UI/student
```

4. Reinicia stack si cambias `.env`:

```bash
make stack-down
make stack-up
```

5. En Atenea (herramienta externa):
- Launch URL: `https://TU-URL-PUBLICA-API/lti/launch`
- Consumer key: la misma configurada en Jutge
- Shared secret: la misma configurada en Jutge

6. Valida el launch tecnico:

```bash
python3 dev-tools/test_lti_launch_flow.py \
	--base-url https://TU-URL-PUBLICA \
	--platform-name atenea-upc \
	--consumer-key jutge-key \
	--consumer-secret jutge-secret
```

Regla rapida:
- Sin Atenea (solo pruebas locales): no hace falta ngrok.
- Con Atenea real: ngrok es obligatorio para exponer una URL publica.

Guia completa paso a paso:
- [ATENEA LTI RUNBOOK](docs/ATENEA_LTI_RUNBOOK.md)

## Project Structure

```
jutge/
├── src/                    # Main source code
│   ├── api/               # FastAPI backend
│   ├── compiler.py        # GCC compilation
│   ├── runner.py          # Program execution
│   ├── evaluator.py       # Output evaluation
│   ├── judge.py           # CLI judge
│   ├── judge_v2.py        # Advanced judge (API/Docker)
│   └── worker.py          # Async job processor
│
├── submissions/           # User code submissions
├── test_cases/           # Test case definitions
├── tests/                # Original test suite
│
├── docs/                 # 📁 Documentation & guides
│   ├── README.md
│   ├── QUICKSTART.md
│   ├── API_README.md
│   ├── ASYNC_SYSTEM_GUIDE.md
│   ├── DBEAVER_SETUP.md
│   └── ... (other docs)
│
├── dev-tools/           # 📁 Development utilities
│   ├── test_*.py        # Test scripts
│   ├── monitor.py       # DB CLI monitor
│   ├── validate_tests.py
│   └── ... (other tools)
│
├── Dockerfile
├── docker-compose-api.yml
├── docker-compose.yml
├── requirements-api.txt
└── run_in_docker.py
```

## Key Modules

- **judge.py**: Simple CLI judge (for local testing)
- **judge_v2.py**: Production judge with detailed verdicts (AC/WA/CE/TLE/RTE/OOM)
- **API**: FastAPI with JWT auth, database models, async job queue
- **Worker**: Processes jobs in background, evaluates in Docker containers

## Documentation

For detailed guides, see the `docs/` folder:

- [Quick Start Guide](docs/QUICKSTART.md)
- [API Reference](docs/API_README.md)
- [Async System Architecture](docs/ASYNC_SYSTEM_GUIDE.md)
- [Database Monitoring with DBeaver](docs/DBEAVER_SETUP.md)
- [Integration Guide](docs/INTEGRATION_GUIDE.md)
- [Development Notes](docs/DEVELOPMENT.md)

## Teacher Admin Panel (Streamlit)

`admin_streamlit.py` provides a teacher dashboard in Catalan with:

- Topic management (`/topics`): create, inline edit, delete selected.
- Exercise management (`/exercises`): create, inline edit, delete selected.
- Test cases management (`/test_cases`): view public test count and add extra tests.
- Student list (`/students`): full list of registered students for teacher accounts.

Important UX note:
- Streamlit `data_editor` may not commit a cell if the user clicks save while the cell is still active.
- Mitigation implemented: explicit inline hint (“prem Enter o fes clic fora...”) and contextual success messages shown below the component that triggered the action.

## Student Submission Panel (Streamlit)

`student_streamlit.py` provides a student-facing submission page with:

- Login de alumno vía `/token`.
- Listado de ejercicios con estado de completado.
- Envío de archivo `.c` para evaluación asíncrona (`/submissions`).
- Historial de entregas del alumno (`/me/submissions`).

## Development

Test scripts and monitoring tools are in `dev-tools/`:

```bash
# Run end-to-end test
python3 dev-tools/test_e2e_docker.py

# Monitor database
python3 dev-tools/monitor.py

# Query specific run results
python3 dev-tools/query_run.py
```

## Database

PostgreSQL connection:
- Host: `localhost`
- Port: `5432`
- Database: `jutge_db`
- User: `jutge`
- Password: `jutge_pass`

Use DBeaver GUI for easy browsing: [Setup Guide](docs/DBEAVER_SETUP.md)

## Architecture

The system has 3 components:

1. **API (FastAPI)**: REST endpoints for users, exercises, submissions
2. **Database (PostgreSQL)**: Stores users, exercises, test cases, runs, jobs
3. **Worker**: Polls jobs, evaluates code in Docker, stores results

See [ASYNC_SYSTEM_GUIDE.md](docs/ASYNC_SYSTEM_GUIDE.md) for detailed flow.
