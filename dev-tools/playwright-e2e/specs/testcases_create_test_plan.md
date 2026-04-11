# Plan de Pruebas - Creación de Test Cases

## Application Overview
Este plan valida dos formas de alta de jocs de prova en el panel Streamlit de Jutge: interfaz manual e importación JSON.

## Seed
- Archivo base: `tests/seed.spec.ts`
- Objetivo: confirmar login válido y dashboard operativo.

## Test Scenarios

### 1. Crear joc de prova desde interfaz auxiliar (manual)
**File:** `tests/admin/testcases-create.spec.ts`

**Steps:**
1. Iniciar sesión como profesor.
2. Crear o seleccionar un exercise.
3. Completar formulario manual del joc de prova.
   - expect: el joc de prova aparece en el listado del exercise seleccionado.

### 2. Crear joc de prova desde importador JSON
**File:** `tests/admin/testcases-create.spec.ts`

**Steps:**
1. Iniciar sesión como profesor.
2. Crear o seleccionar un exercise.
3. Importar JSON válido de jocs de prova.
   - expect: el joc de prova importado aparece en el listado del exercise seleccionado.