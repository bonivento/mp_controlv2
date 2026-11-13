# Sigmalena

**Sigmalena** (sigma + Magdalena) es una aplicación web de *Control estadístico de procesos* (CEP), con la identidad cromática de la Universidad del Magdalena (azul `#004A87` y complemento naranja `#FF9400`). Construye gráficos de control por variables (X-barra-R, X-barra-S, I-MR) y por atributos (p, np, c, u) en Fase I y Fase II; valida los supuestos de normalidad e independencia; calcula Cp, Cpk, Cpl, Cpu, Pp, Ppk y la fracción no conforme; diseña gráficos con ARL0, ARL1 y ATS; diseña y evalúa planes de muestreo de aceptación; y reúne los resultados en un reporte imprimible y exportable a Excel.

Además:

- **Modo invitado:** en la pantalla de acceso, «Continuar como invitado» entra sin correo (inicio de sesión anónimo de Supabase). El invitado es un usuario real con sesión, así que el aislamiento por RLS y la verificación del JWT en la API no cambian; puede convertirse en cuenta con «Crear cuenta para conservar mis datos» sin perder sus estudios.
- **Ingreso manual de datos:** la pantalla Datos tiene la pestaña «Escribir o pegar datos», una tabla editable (hasta 2000 filas y 50 columnas) que acepta bloques pegados desde Excel con coma decimal y sigue después el mismo camino que un archivo.

Es el trabajo final de la asignatura Control Estadístico de Procesos. El enunciado y la rúbrica están en [TRABAJO FINAL.md](TRABAJO%20FINAL.md).

**En producción:** <https://cep-web.vercel.app> (web) y <https://cep-api-xi.vercel.app/api/health> (API). El código está en <https://github.com/bonivento/mp_controlv2>.

## Entregables

| Entregable | Dónde está |
|---|---|
| Programa y código fuente | Este repositorio (`api/`, `web/`, `supabase/`) |
| Informe técnico APA | [docs/informe/informe-tecnico.md](docs/informe/informe-tecnico.md) |
| Manual de usuario | [docs/manual/manual-usuario.md](docs/manual/manual-usuario.md) |
| Guion del video | [docs/video/guion.md](docs/video/guion.md) |
| Datos de prueba | [data/ejemplos/](data/ejemplos/) (sintéticos; ver su README) |
| Evidencia de ejecución | [docs/validacion.md](docs/validacion.md) y las salidas guardadas en [docs/informe/anexos/salidas/](docs/informe/anexos/salidas/) |

## Qué hace, por módulo

| Módulo | Pantalla | Ruta de la API |
|---|---|---|
| 1. Gestión de datos | Datos | `/api/data/parse`, `/api/data/summary`, `/api/data/summary/attributes` |
| 2. Gráficos por variables | Variables | `/api/charts/variables` |
| 3. Gráficos por atributos | Atributos | `/api/charts/attributes`, `/api/charts/attributes/recommend` |
| 4. Validación de supuestos | Supuestos | `/api/assumptions` |
| 5. Capacidad del proceso | Capacidad | `/api/capability` |
| 6. Diseño de gráficos (ARL, ATS) | Diseño | `/api/design/arl`, `/api/design/compare` |
| 7. Muestreo de aceptación | Muestreo | `/api/sampling/single/design`, `/api/sampling/single/evaluate`, `/api/sampling/double/evaluate` |
| 8. Reportes | Reporte | `/api/reports/excel` (el PDF sale de la propia página con «Imprimir / guardar PDF») |

## Arquitectura

```
Navegador -> web (Next.js) --supabase-js + RLS--> Supabase (Auth y Postgres)
                  |
                  +-- /api/* (rewrite) --> api (FastAPI, sin estado)
```

- `web/` muestra la interfaz, gestiona la sesión y guarda estudios, datos, límites congelados y análisis en Supabase. No hace cálculos estadísticos.
- `api/` hace todos los cálculos y no guarda nada. Es determinista: la misma entrada produce la misma salida (la simulación de ARL usa semilla fija).
- Supabase da el inicio de sesión y aísla los datos de cada usuario con políticas de seguridad por filas (RLS).

Detalle en [docs/arquitectura.md](docs/arquitectura.md) y en [docs/contrato-api.md](docs/contrato-api.md).

## Estructura del código

| Carpeta | Contenido |
|---|---|
| [api/](api/) | Backend en FastAPI |
| [api/app/spc/](api/app/spc/) | Librería estadística en Python puro: `constants.py` (d2, d3, c4, A2, A3, B3 a B6, D3, D4), `variables.py` (X-barra-R, X-barra-S, I-MR), `attributes.py` (p, np, c, u), `phases.py` (Fase I y Fase II), `rules.py` (Western Electric y Nelson), `assumptions.py`, `capability.py`, `design.py` (ARL y ATS), `sampling.py`, `descriptive.py`, `interpretation.py` |
| [api/app/schemas/](api/app/schemas/) | Contrato Pydantic de entradas y salidas, un archivo por módulo |
| [api/app/routers/](api/app/routers/) | Rutas HTTP que conectan el contrato con `spc/` |
| [api/app/auth.py](api/app/auth.py), [files.py](api/app/files.py), [excel_report.py](api/app/excel_report.py) | Verificación del JWT de Supabase, lectura de CSV y Excel, exportación a Excel |
| [api/tests/](api/tests/) | Pruebas con pytest: `spc/` (librería), `routers/` (HTTP) y `test_contract.py` |
| [web/app/](web/app/) | Páginas de Next.js: acceso, estudios y una página por módulo |
| [web/components/](web/components/) | Gráficos Plotly, carga de datos, resumen, reporte y componentes de interfaz |
| [web/lib/](web/lib/) | Cliente de la API tipado, acceso a Supabase y modo de demostración |
| [supabase/](supabase/) | Migraciones SQL, políticas RLS, datos semilla y pruebas de aislamiento |
| [data/](data/) | Datos sintéticos de prueba y su generador |
| [docs/](docs/) | Plan, arquitectura, despliegue, informe, manual y guion |

Cada fórmula de `api/app/spc/` cita en su docstring su fuente (Montgomery, *Introduction to Statistical Quality Control*, 6.ª edición, por capítulo; la lista completa está en [docs/fundamentos-estadisticos.md](docs/fundamentos-estadisticos.md)) y tiene una prueba contra un resultado conocido.

## Requisitos

| Herramienta | Versión | Para qué |
|---|---|---|
| Python | 3.12 | API |
| uv | reciente | Crear el entorno virtual e instalar dependencias de la API |
| Node.js | 20 o superior | Web |
| npm | el que trae Node | Dependencias de la web |
| Cuenta de Supabase | gratuita | Acceso y base de datos (opcional en local: hay modo de demostración) |

## Instalación y ejecución local

La ruta del proyecto contiene un espacio (`control v2`): ponla entre comillas en la terminal.

```bash
cd "control v2"

# 1. API en http://localhost:8000  (documentación interactiva en /api/docs)
cd api
uv venv --python 3.12 .venv
uv pip install -r requirements-dev.txt
AUTH_DISABLED=1 .venv/bin/uvicorn main:app --reload --port 8000

# 2. Web en http://localhost:3000 (en otra terminal)
cd web
cp .env.example .env.local     # completar según el modo elegido (abajo)
npm install
npm run dev
```

`AUTH_DISABLED=1` desactiva la verificación del JWT y solo sirve en local. Nunca debe ponerse en producción.

### Modo de la web

| Modo | Configuración en `web/.env.local` | Qué se guarda y dónde |
|---|---|---|
| Real | `NEXT_PUBLIC_SUPABASE_URL` y `NEXT_PUBLIC_SUPABASE_ANON_KEY` con los valores del proyecto de Supabase | En Supabase, con inicio de sesión y RLS. El modo invitado exige habilitar los inicios de sesión anónimos en el proyecto (ver nota abajo) |
| Demostración | `NEXT_PUBLIC_DEMO_MODE=1` | En el `localStorage` del navegador; la pantalla de acceso ofrece una cuenta de ejemplo con estudios sintéticos, y el invitado es local a ese navegador |

> **Nota sobre el invitado en modo real:** `supabase/config.toml` trae `enable_anonymous_sign_ins = false`. Para que «Continuar como invitado» funcione contra Supabase hay que activar *Anonymous sign-ins* en el proyecto (Authentication, Providers); de lo contrario la web muestra un mensaje de error al pulsarlo.

`API_URL` apunta a la API (en local, `http://localhost:8000`). Las variables completas están en [docs/despliegue.md](docs/despliegue.md).

## Librerías

**API** (`api/requirements.txt`): `fastapi`, `python-multipart`, `numpy`, `scipy`, `openpyxl`, `pyjwt[crypto]`. No se usan pandas ni statsmodels: el paquete de Vercel no puede superar 250 MB. `requirements-dev.txt` añade las herramientas de prueba.

**Web** (`web/package.json`): `next`, `react`, `react-dom`, `@supabase/supabase-js`, `@supabase/ssr`, `plotly.js-basic-dist-min`, `react-plotly.js`. Para desarrollo: `typescript`, `tailwindcss`, `eslint`, `openapi-typescript` y `@playwright/test`.

## Datos de prueba

La carpeta [data/ejemplos/](data/ejemplos/) tiene 13 conjuntos sintéticos (CSV y XLSX) del llenado de envases de 500 g de salsa, con especificaciones LIE 495 g y LSE 505 g. Cada archivo cubre un gráfico o un problema distinto (datos sucios, no normales, autocorrelacionados) e indica en su [README](data/ejemplos/README.md) el resultado esperado. Todos son sintéticos y se regeneran con:

```bash
api/.venv/bin/python data/generar_ejemplos.py
```

Los datos de una empresa real no se suben al repositorio. Para recolectarlos, usar los formatos de [docs/empresa/](docs/empresa/).

## Pruebas

```bash
cd api
.venv/bin/python -m pytest -q          # librería spc, rutas HTTP y contrato

cd web
npm run lint && npm run build          # verificación estática y compilación
npx playwright test                    # extremo a extremo (requiere web y API en marcha)
```

La última corrida de la suite de la API entregó `986 passed, 1 skipped`: 986 pruebas que pasan, una omitida y ninguna marcada como fallo esperado (ver [docs/validacion.md](docs/validacion.md)). Esas pruebas incluyen `api/tests/validation/`, la revisión estadística independiente: un revisor recalculó por otro camino constantes, límites, índices, ARL, reglas de corrida y planes de muestreo, encontró errores (por ejemplo, los grados de libertad de los intervalos de capacidad y los valores críticos de Anderson-Darling) y se corrigieron; en una segunda pasada midió por simulación la cobertura de los intervalos corregidos (0,944 a 0,955) y registró otros diez hallazgos, casi todos de redacción de la interpretación, también corregidos.

## Reproducir las cifras del informe

Todas las cifras del informe salen de respuestas reales de la API guardadas en `docs/informe/anexos/salidas/`.

```bash
cd api && AUTH_DISABLED=1 .venv/bin/uvicorn main:app --port 8040     # terminal 1
api/.venv/bin/python docs/informe/anexos/generar_salidas.py          # terminal 2: regenera los JSON
python docs/informe/anexos/generar_figuras.py                        # requiere matplotlib en un entorno aparte (no está en api/.venv)
```

`generar_figuras.py` solo dibuja lo que devolvió la API; con un entorno de `uv` aparte: `uv venv /ruta/figenv && uv pip install --python /ruta/figenv/bin/python matplotlib`.

## Despliegue

La web y la API se despliegan como dos proyectos de Vercel desde el mismo repositorio, con Supabase como base de datos. Los pasos están en [docs/despliegue.md](docs/despliegue.md).

## Evidencia de ejecución

- [docs/validacion.md](docs/validacion.md): revisión estadística independiente: resultados del software contra cálculos propios del revisor, errores encontrados y su estado de corrección.
- [docs/fundamentos-estadisticos.md](docs/fundamentos-estadisticos.md): fórmula y fuente de cada cálculo.
- [docs/informe/anexos/salidas/](docs/informe/anexos/salidas/): peticiones y respuestas reales usadas en el informe.
- [docs/capturas/](docs/capturas/): capturas de pantalla de cada módulo.

## Documentación

| Documento | Para qué |
|---|---|
| [docs/PLAN.md](docs/PLAN.md) | Plan aprobado: alcance y decisiones |
| [docs/arquitectura.md](docs/arquitectura.md) | Reparto de responsabilidades |
| [docs/contrato-api.md](docs/contrato-api.md) | Rutas y convenciones de la API |
| [docs/despliegue.md](docs/despliegue.md) | Ejecución local y despliegue |
| [docs/manual/manual-usuario.md](docs/manual/manual-usuario.md) | Cómo usar el software |
| [docs/informe/informe-tecnico.md](docs/informe/informe-tecnico.md) | Informe técnico en normas APA |
| [docs/video/guion.md](docs/video/guion.md) | Guion del video de marketing |
| [docs/empresa/](docs/empresa/) | Guía de visita, formato de recolección, confidencialidad y plan de muestreo |

## Equipo

> **POR COMPLETAR: nombres de los integrantes, programa, docente y datos de contacto del equipo.**
