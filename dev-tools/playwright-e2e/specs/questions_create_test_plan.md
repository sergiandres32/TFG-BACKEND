# Plan de Pruebas - Creación de Questions

## Application Overview
Este plan valida dos formas de alta de preguntas tipo test en el panel Streamlit de Jutge: interfaz manual e importación JSON.

## Seed
- Archivo base: `tests/seed.spec.ts`
- Objetivo: confirmar login válido y dashboard operativo.

## Test Scenarios

### 1. Crear question desde interfaz auxiliar (manual)
**File:** `tests/admin/questions-create.spec.ts`

**Steps:**
1. Iniciar sesión como profesor.
2. Crear o seleccionar un topic.
3. Completar formulario manual de pregunta.
   - expect: la pregunta aparece listada para el topic seleccionado.

### 2. Crear question desde importador JSON
**File:** `tests/admin/questions-create.spec.ts`

**Steps:**
1. Iniciar sesión como profesor.
2. Crear o seleccionar un topic.
3. Importar JSON válido de preguntas.
   - expect: la pregunta importada aparece listada para el topic seleccionado.