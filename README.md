# Software CEP

Aplicación web de Control Estadístico de Procesos: gráficos de control por variables y por atributos en Fase I y Fase II, validación de supuestos, capacidad de proceso, diseño de gráficos con ARL y ATS, muestreo de aceptación y reportes.

Trabajo final de la asignatura Control Estadístico de Procesos. El enunciado está en [TRABAJO FINAL.md](TRABAJO%20FINAL.md).

> **Estado:** base del proyecto lista (estructura, contrato de la API, esquema de base de datos). Los módulos se construyen por olas según [docs/ejecucion-agentes.md](docs/ejecucion-agentes.md).

## Estructura

| Carpeta | Contenido |
|---|---|
| [api/](api/) | Backend en FastAPI. `app/spc/` es la librería estadística, `app/schemas/` el contrato, `app/routers/` las rutas |
| [web/](web/) | Frontend en Next.js |
| [supabase/](supabase/) | Migraciones SQL y políticas de seguridad |
| [data/](data/) | Datos de prueba sintéticos y casos de referencia |
| [docs/](docs/) | Plan, arquitectura, despliegue, informe, manual y guion |
| [.claude/agents/](.claude/agents/) | Agentes que construyen el proyecto en paralelo |

## Documentación

| Documento | Para qué |
|---|---|
| [docs/PLAN.md](docs/PLAN.md) | Plan aprobado: alcance, decisiones y olas de trabajo |
| [docs/arquitectura.md](docs/arquitectura.md) | Cómo se reparten las responsabilidades y por qué |
| [docs/contrato-api.md](docs/contrato-api.md) | Rutas de la API y convenciones |
| [docs/ejecucion-agentes.md](docs/ejecucion-agentes.md) | Cómo lanzar cada ola y qué revisar entre una y otra |
| [docs/despliegue.md](docs/despliegue.md) | Ejecución local y despliegue en Supabase y Vercel |

## Inicio rápido

```bash
# API
cd api
uv venv --python 3.12 .venv && uv pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
AUTH_DISABLED=1 .venv/bin/uvicorn main:app --reload --port 8000

# Web
cd web
npm install
npm run dev
```

Detalle y variables de entorno en [docs/despliegue.md](docs/despliegue.md).
