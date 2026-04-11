COMPOSE_FILE := docker-compose-api.yml
COMPOSE := docker-compose
PYTHON := python3
STREAMLIT_PID_FILE := .streamlit_admin.pid
STREAMLIT_LOG_FILE := .streamlit_admin.log
POSTMAN_ENV := dev-tools/postman/jutge_e2e.local.postman_environment.json
NEWMAN_IMAGE := postman/newman:alpine
NEWMAN_DOCKER := docker run --rm --network host -v $(PWD):/etc/newman -w /etc/newman $(NEWMAN_IMAGE)
PLAYWRIGHT_TS_DIR := dev-tools/playwright-e2e

.PHONY: help stack-up stack-down stack-logs db-clean db-seed db-reset-seed api-test-base-flow api-test-comprehensive ui-test-streamlit-smoke ui-test-streamlit-smoke-venv playwright-install playwright-install-venv playwright-ts-install playwright-ts-browser-install playwright-ts-setup ui-test-streamlit-smoke-ts ui-test-streamlit-topics-ts ui-test-streamlit-questions-ts ui-test-streamlit-exercises-ts ui-test-streamlit-testcases-ts ui-test-streamlit-smoke-ts-headed ui-test-streamlit-topics-ts-headed ui-test-streamlit-questions-ts-headed ui-test-streamlit-exercises-ts-headed ui-test-streamlit-testcases-ts-headed ui-test-streamlit-ts-all ui-test-streamlit-ts-all-headed newman-contract newman-contract-errors newman-e2e newman-all newman-local-contract newman-local-contract-errors newman-local-e2e newman-local-all newman-docker-contract newman-docker-contract-errors newman-docker-e2e newman-docker-all openapi-export release-runtime release-runtime-version release-runtime-dir release-runtime-dir-version

help:
	@echo "Comandos disponibles:"
	@echo "  make stack-up         # Levanta API + worker + DB y arranca Streamlit admin en background"
	@echo "  make stack-down       # Apaga stack Docker y detiene Streamlit admin en background"
	@echo "  make stack-logs       # Muestra logs en tiempo real del stack"
	@echo "  make db-clean         # Limpia DB (drop/create tablas)"
	@echo "  make db-seed          # Carga profesor + ejercicios + test cases"
	@echo "  make db-reset-seed    # Ejecuta clean + seed en cadena"
	@echo "  make api-test-base-flow # Prueba E2E: Alumno A (todo) y Alumno B (sum + fallo sort)"
	@echo "  make api-test-comprehensive # Suite E2E completa: profesor + 3 alumnos + seguridad"
	@echo "  make playwright-install # Instala navegador Chromium para Playwright"
	@echo "  make playwright-install-venv # Instala Chromium usando .venv/bin/python"
	@echo "  make ui-test-streamlit-smoke # Smoke test UI de Streamlit (Playwright)"
	@echo "  make ui-test-streamlit-smoke-venv # Smoke test UI usando .venv/bin/python"
	@echo "  make playwright-ts-install # Instala dependencias npm de Playwright TS"
	@echo "  make playwright-ts-browser-install # Instala Chromium para la suite TS"
	@echo "  make playwright-ts-setup # Ejecuta install + browser-install para la suite TS"
	@echo "  make ui-test-streamlit-smoke-ts # Smoke TS del admin Streamlit"
	@echo "  make ui-test-streamlit-topics-ts # E2E TS: alta manual + JSON de topics"
	@echo "  make ui-test-streamlit-questions-ts # E2E TS: alta manual + JSON de questions"
	@echo "  make ui-test-streamlit-exercises-ts # E2E TS: alta manual + JSON de exercises"
	@echo "  make ui-test-streamlit-testcases-ts # E2E TS: alta manual + JSON de jocs de prova"
	@echo "  make ui-test-streamlit-ts-all # Ejecuta todas las specs TS del admin"
	@echo "  make ui-test-streamlit-ts-all-headed # Ejecuta todas las specs TS del admin con navegador visible"
	@echo "  make newman-contract  # Newman dockerizado: contratos core (PR)"
	@echo "  make newman-contract-errors # Newman dockerizado: contratos negativos (PR)"
	@echo "  make newman-e2e       # Newman dockerizado: flujo E2E multi-actor"
	@echo "  make newman-all       # Newman dockerizado: contract + contract-errors + e2e"
	@echo "  make newman-local-all # Newman local (si ya lo tienes instalado)"
	@echo "  make openapi-export   # Exporta OpenAPI runtime a docs/openapi.json"
	@echo "  make release-runtime  # Genera tar.gz runtime mínimo (whitelist)"
	@echo "  make release-runtime-version VERSION=vX.Y.Z # Genera release con versión fija"
	@echo "  make release-runtime-dir # Genera carpeta runtime mínima (sin zip)"
	@echo "  make release-runtime-dir-version VERSION=vX.Y.Z # Genera carpeta release con versión fija"

stack-up:
	$(COMPOSE) -f $(COMPOSE_FILE) up -d --build
	@if [ -f $(STREAMLIT_PID_FILE) ] && kill -0 $$(cat $(STREAMLIT_PID_FILE)) 2>/dev/null; then \
		echo "Streamlit admin ya esta en ejecucion (PID $$(cat $(STREAMLIT_PID_FILE)))."; \
	else \
		nohup $(PYTHON) -m streamlit run admin_streamlit.py > $(STREAMLIT_LOG_FILE) 2>&1 & echo $$! > $(STREAMLIT_PID_FILE); \
		echo "Streamlit admin lanzado en background (PID $$(cat $(STREAMLIT_PID_FILE)))."; \
		echo "Logs: tail -f $(STREAMLIT_LOG_FILE)"; \
	fi

stack-down:
	$(COMPOSE) -f $(COMPOSE_FILE) down
	@if [ -f $(STREAMLIT_PID_FILE) ]; then \
		kill $$(cat $(STREAMLIT_PID_FILE)) 2>/dev/null || true; \
		rm -f $(STREAMLIT_PID_FILE); \
		echo "Streamlit admin detenido."; \
	fi

stack-logs:
	$(COMPOSE) -f $(COMPOSE_FILE) logs -f

db-clean:
	$(COMPOSE) -f $(COMPOSE_FILE) run --rm api $(PYTHON) dev-tools/clean_db.py

db-seed:
	$(COMPOSE) -f $(COMPOSE_FILE) run --rm api $(PYTHON) dev-tools/seed_db.py

db-reset-seed:
	$(COMPOSE) -f $(COMPOSE_FILE) run --rm api $(PYTHON) dev-tools/reset_and_seed.py

api-test-base-flow:
	$(PYTHON) dev-tools/test_base_flow_api.py

api-test-comprehensive:
	$(PYTHON) dev-tools/test_e2e_comprehensive.py

playwright-install:
	$(PYTHON) -m playwright install chromium

playwright-install-venv:
	.venv/bin/python -m playwright install chromium

ui-test-streamlit-smoke:
	$(PYTHON) dev-tools/test_streamlit_ui_smoke.py

ui-test-streamlit-smoke-venv:
	.venv/bin/python dev-tools/test_streamlit_ui_smoke.py

playwright-ts-install:
	cd $(PLAYWRIGHT_TS_DIR) && npm ci

playwright-ts-browser-install:
	cd $(PLAYWRIGHT_TS_DIR) && npx playwright install chromium

playwright-ts-setup: playwright-ts-install playwright-ts-browser-install

ui-test-streamlit-smoke-ts:
	cd $(PLAYWRIGHT_TS_DIR) && npx playwright test tests/admin/login-dashboard-smoke.spec.ts

ui-test-streamlit-topics-ts:
	cd $(PLAYWRIGHT_TS_DIR) && npx playwright test tests/admin/topics-create.spec.ts

ui-test-streamlit-questions-ts:
	cd $(PLAYWRIGHT_TS_DIR) && npx playwright test tests/admin/questions-create.spec.ts

ui-test-streamlit-exercises-ts:
	cd $(PLAYWRIGHT_TS_DIR) && npx playwright test tests/admin/exercises-create.spec.ts

ui-test-streamlit-testcases-ts:
	cd $(PLAYWRIGHT_TS_DIR) && npx playwright test tests/admin/testcases-create.spec.ts

ui-test-streamlit-smoke-ts-headed:
	cd $(PLAYWRIGHT_TS_DIR) && npx playwright test tests/admin/login-dashboard-smoke.spec.ts --headed

ui-test-streamlit-topics-ts-headed:
	cd $(PLAYWRIGHT_TS_DIR) && npx playwright test tests/admin/topics-create.spec.ts --headed

ui-test-streamlit-questions-ts-headed:
	cd $(PLAYWRIGHT_TS_DIR) && npx playwright test tests/admin/questions-create.spec.ts --headed

ui-test-streamlit-exercises-ts-headed:
	cd $(PLAYWRIGHT_TS_DIR) && npx playwright test tests/admin/exercises-create.spec.ts --headed

ui-test-streamlit-testcases-ts-headed:
	cd $(PLAYWRIGHT_TS_DIR) && npx playwright test tests/admin/testcases-create.spec.ts --headed

ui-test-streamlit-ts-all:
	cd $(PLAYWRIGHT_TS_DIR) && npx playwright test tests/admin

ui-test-streamlit-ts-all-headed:
	cd $(PLAYWRIGHT_TS_DIR) && npx playwright test tests/admin --headed

newman-contract:
	$(NEWMAN_DOCKER) run dev-tools/postman/jutge_api_contract.postman_collection.json -e $(POSTMAN_ENV)

newman-contract-errors:
	$(NEWMAN_DOCKER) run dev-tools/postman/jutge_api_contract_errors.postman_collection.json -e $(POSTMAN_ENV)

newman-e2e:
	$(NEWMAN_DOCKER) run dev-tools/postman/jutge_e2e.postman_collection.json -e $(POSTMAN_ENV) --delay-request 3000

newman-all: newman-contract newman-contract-errors newman-e2e

newman-local-contract:
	newman run dev-tools/postman/jutge_api_contract.postman_collection.json -e $(POSTMAN_ENV)

newman-local-contract-errors:
	newman run dev-tools/postman/jutge_api_contract_errors.postman_collection.json -e $(POSTMAN_ENV)

newman-local-e2e:
	newman run dev-tools/postman/jutge_e2e.postman_collection.json -e $(POSTMAN_ENV) --delay-request 3000

newman-local-all: newman-local-contract newman-local-contract-errors newman-local-e2e

newman-docker-contract:
	$(NEWMAN_DOCKER) run dev-tools/postman/jutge_api_contract.postman_collection.json -e $(POSTMAN_ENV)

newman-docker-contract-errors:
	$(NEWMAN_DOCKER) run dev-tools/postman/jutge_api_contract_errors.postman_collection.json -e $(POSTMAN_ENV)

newman-docker-e2e:
	$(NEWMAN_DOCKER) run dev-tools/postman/jutge_e2e.postman_collection.json -e $(POSTMAN_ENV) --delay-request 3000

newman-docker-all: newman-docker-contract newman-docker-contract-errors newman-docker-e2e

openapi-export:
	$(PYTHON) -c "import json, urllib.request; data=json.loads(urllib.request.urlopen('http://localhost:8000/openapi.json', timeout=30).read().decode('utf-8')); open('docs/openapi.json','w',encoding='utf-8').write(json.dumps(data, ensure_ascii=False, indent=2)); print('docs/openapi.json actualizado ✅')"

release-runtime:
	bash release/build_release.sh

release-runtime-version:
	bash release/build_release.sh $(VERSION)

release-runtime-dir:
	bash release/build_release_dir.sh

release-runtime-dir-version:
	bash release/build_release_dir.sh $(VERSION)
