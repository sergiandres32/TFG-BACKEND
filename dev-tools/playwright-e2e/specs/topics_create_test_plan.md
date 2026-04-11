# Plan de Pruebas - Creación de Topics

## Application Overview
Este plan valida dos formas de alta de topics (temes de asignatura) en el panel Streamlit de Jutge: interfaz manual e importación JSON.

## Seed
- Archivo base: `tests/seed.spec.ts`
- Objetivo: confirmar login válido y dashboard operativo.

## Test Scenarios

### 1. Crear topic desde interfaz auxiliar (manual)
**File:** `tests/admin/topics-create.spec.ts`

**Steps:**
1. Iniciar sesión como profesor.
2. Ir al bloque "Crear tema".
3. Completar formulario manual y confirmar.
   - expect: el topic aparece en la tabla de "Temes".

### 2. Crear topic desde importador JSON
**File:** `tests/admin/topics-create.spec.ts`

**Steps:**
1. Iniciar sesión como profesor.
2. Activar "Importar des de JSON" en el bloque de temes.
3. Enviar un JSON válido con un topic.
   - expect: el topic importado aparece en la tabla de "Temes".
