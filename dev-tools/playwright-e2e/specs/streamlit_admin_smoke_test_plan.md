# Plan de Pruebas - Streamlit Admin Smoke

## Application Overview
Este plan valida el acceso del profesor al panel de administración de Jutge en Streamlit.

## Seed
- Archivo base: `tests/seed.spec.ts`
- Objetivo: confirmar carga de `http://localhost:8501` y existencia del formulario de login.

## Test Scenarios

### 1. Login de profesor y carga de dashboard
**File:** `tests/admin/login-dashboard-smoke.spec.ts`

**Steps:**
1. Navegar a la home de Streamlit.
   - expect: aparece título "Jutge Admin" y campos de autenticación.
2. Introducir credenciales de profesor.
   - expect: botón "Inicia sessió" ejecuta login.
3. Validar dashboard.
   - expect: aparece "Tauler d'administració" y secciones "Temes", "Exercicis", "Preguntes tipus test".
