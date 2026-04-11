# Plan de Pruebas - Creación de Exercises

## Application Overview
Este plan valida dos formas de alta de ejercicios en el panel Streamlit de Jutge: interfaz manual e importación JSON.

## Seed
- Archivo base: `tests/seed.spec.ts`
- Objetivo: confirmar login válido y dashboard operativo.

## Test Scenarios

### 1. Crear exercise desde interfaz auxiliar (manual)
**File:** `tests/admin/exercises-create.spec.ts`

**Steps:**
1. Iniciar sesión como profesor.
2. Crear o seleccionar un topic.
3. Completar formulario manual de ejercicio.
   - expect: el ejercicio aparece en el listado de ejercicios.

### 2. Crear exercise desde importador JSON
**File:** `tests/admin/exercises-create.spec.ts`

**Steps:**
1. Iniciar sesión como profesor.
2. Crear o seleccionar un topic.
3. Importar JSON válido de ejercicios.
   - expect: el ejercicio importado aparece en el listado de ejercicios.