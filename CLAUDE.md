# Software CEP v2

Trabajo final de Control Estadístico de Procesos. El enunciado y la rúbrica están en `TRABAJO FINAL.md`; el plan aprobado, en `docs/PLAN.md`. Léelos antes de trabajar.

## Arquitectura en una línea

`web/` (Next.js) guarda en Supabase con `supabase-js` bajo RLS y pide los cálculos a `api/` (FastAPI, sin estado). Detalle en `docs/arquitectura.md`.

## Reglas que no se negocian

1. **El contrato manda.** `api/app/schemas/` define entradas y salidas. Solo la sesión principal lo edita. Si un agente necesita un cambio, lo describe en su reporte final y no lo aplica.
2. **Cada agente escribe solo en sus carpetas** (tabla de abajo). Leer se puede en todo el repo.
3. **`api/app/spc/` es Python puro**: sin FastAPI, sin Pydantic, sin acceso a red ni a disco. Recibe listas o arreglos y devuelve dataclasses o diccionarios.
4. **Dependencias de la API**: solo las de `api/requirements.txt`. Nada de pandas ni statsmodels (límite de 250 MB en Vercel).
5. **Toda fórmula lleva su fuente** en el docstring (Montgomery, *Introduction to Statistical Quality Control*, capítulo y ecuación) y una prueba contra un resultado conocido.
6. **Idioma**: interfaz, comentarios, docstrings y documentos en español; nombres de variables, funciones y archivos de código en inglés.
7. **Nunca NaN ni infinito en una respuesta**: lo que no se puede calcular va como `null` con una advertencia en `interpretation.warnings`.
8. **Datos sintéticos siempre marcados** como tales en el nombre del archivo y en el documento que los use.
9. **Secretos fuera de git**: van en `.env.local`. Cada variable nueva se documenta en `.env.example`.
10. No hacer commit ni push salvo que la sesión principal lo pida.

## Dueños de carpetas

| Carpeta o archivo | Dueño |
|---|---|
| `api/app/schemas/`, `CLAUDE.md`, `docs/PLAN.md`, `docs/contrato-api.md`, `docs/arquitectura.md` | sesión principal |
| `api/app/spc/{constants,variables,attributes,phases,rules}.py` y sus `api/tests/spc/test_*.py` | `spc-graficos` |
| `api/app/spc/{assumptions,capability,design,sampling,interpretation,descriptive}.py` y sus tests | `spc-analisis` |
| `api/main.py`, `api/app/{auth,files,excel_report}.py`, `api/app/routers/`, `api/tests/routers/`, `api/.env.example` | `backend-api` |
| `supabase/`, `web/lib/database-types.ts` | `supabase-db` |
| `web/` excepto lo que sigue | `frontend-web` |
| `web/e2e/`, `web/playwright.config.ts`, `docs/pruebas-e2e.md`, `docs/capturas/` | `qa-e2e` |
| `data/`, `docs/empresa/` | `datos-prueba` |
| `docs/validacion.md`, `docs/fundamentos-estadisticos.md`, `api/tests/validation/` | `validador-estadistico` |
| `docs/informe/`, `docs/manual/`, `docs/video/`, `README.md` | `redactor-docs` |

## Comandos

```bash
# API (Python 3.12 con uv)
cd api
uv venv --python 3.12 .venv && uv pip install -r requirements-dev.txt   # una vez
.venv/bin/python -m pytest -q                                           # pruebas
.venv/bin/uvicorn main:app --reload --port 8000                         # servidor local
.venv/bin/python -c "import json; from main import app; json.dump(app.openapi(), open('openapi.json','w'), indent=1, ensure_ascii=False)"

# Web
cd web
npm run dev          # http://localhost:3000
npm run gen:api      # regenera lib/api-types.ts desde ../api/openapi.json
npm run lint && npm run build
```

`web/` usa Next.js 16, que cambió respecto a versiones anteriores: antes de escribir código de Next hay que leer la guía correspondiente en `web/node_modules/next/dist/docs/` (ver `web/AGENTS.md`).

## Criterio de terminado

Un trabajo está terminado cuando sus pruebas pasan, no rompe las pruebas existentes y el reporte final dice qué se hizo, qué no se hizo y qué cambios de contrato se necesitan.
