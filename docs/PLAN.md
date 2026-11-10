# Plan: Software CEP v2 (trabajo final de Control Estadístico de Procesos)

## Contexto

El enunciado ([TRABAJO FINAL.md](TRABAJO FINAL.md)) exige un software de Control Estadístico de Procesos con 8 módulos, aplicado a una empresa manufacturera, más informe APA, manual de usuario y video. La rúbrica pesa ID1 30 % (software y datos), ID2 40 % (interpretación) e ID3 30 % (conclusiones y juicio de ingeniería).

Existe una v1 en `../control` (Flask + Jinja). Le faltan I-MR, Fase I/II, independencia, ARL/ATS, muestreo de aceptación y pruebas, y tiene una regla de Nelson mal implementada. **Decisión: la v2 se escribe desde cero**; de la v1 solo se toman lecciones de despliegue, no código.

Decisiones ya tomadas:

| Tema | Decisión |
|---|---|
| Arquitectura | Monorepo: `web/` Next.js + TypeScript, `api/` FastAPI + numpy/scipy. Ambos en Vercel (dos proyectos, mismo repositorio) |
| Base de datos | Supabase (Postgres + Auth + RLS) |
| Usuarios | Login con Supabase Auth; cada usuario ve solo sus estudios |
| Empresa | Aún no hay. Se entrega un caso de ejemplo con datos sintéticos marcados como tales y los formatos para recolectar los reales |
| Entregables | Software, informe APA, manual de usuario, guion del video |
| Idioma | Interfaz, comentarios y documentos en español; identificadores de código en inglés |

## Arquitectura

```
Navegador ──> web (Next.js, Vercel) ──supabase-js + RLS──> Supabase (Auth, Postgres)
                    │
                    └── /api/* (rewrite) ──> api (FastAPI, Vercel) ── valida JWT de Supabase
```

- **El backend es un motor de cálculo sin estado.** Recibe datos y parámetros, devuelve resultados e interpretación. No guarda nada.
- **El frontend guarda todo en Supabase** con `supabase-js` bajo RLS: estudios, datos, límites congelados de Fase I, análisis y planes de muestreo.
- **El contrato entre ambos son los esquemas Pydantic** de `api/app/schemas/`, de los que sale el OpenAPI y los tipos TypeScript (`openapi-typescript`). Este contrato se escribe en la Ola 0, antes de lanzar agentes; es lo que permite trabajar en paralelo.
- El frontend llama a `/api/*`; un rewrite de Next lo envía al proyecto `api`, así no hay CORS.

### Estructura de carpetas

```
control v2/
├── CLAUDE.md                     reglas del repo, comandos, dueños de carpetas
├── README.md                     instalación y ejecución (entregable 2)
├── .claude/agents/               definiciones de los agentes (ver tabla)
├── api/
│   ├── main.py                   app FastAPI (entrada de Vercel)
│   ├── requirements.txt          fastapi, numpy, scipy, openpyxl, pyjwt  (sin pandas ni statsmodels)
│   ├── app/
│   │   ├── auth.py               verificación del JWT de Supabase (JWKS)
│   │   ├── schemas/              contrato Pydantic, un archivo por módulo
│   │   ├── routers/              data, variables, attributes, assumptions, capability, design, sampling, reports
│   │   └── spc/                  librería estadística pura, sin FastAPI
│   │       ├── constants.py      d2, d3, c4, A2, A3, B3..B6, D3, D4
│   │       ├── variables.py      X̄-R, X̄-S, I-MR
│   │       ├── attributes.py     p, np, c, u
│   │       ├── phases.py         Fase I (depurar, congelar) y Fase II (monitorear)
│   │       ├── rules.py          Western Electric y Nelson
│   │       ├── assumptions.py    normalidad, independencia, estabilidad
│   │       ├── capability.py     Cp, Cpk, Cpl, Cpu, Pp, Ppk, fracción no conforme
│   │       ├── design.py         ARL0, ARL1, ATS, curvas OC
│   │       ├── sampling.py       planes de muestreo de aceptación
│   │       └── interpretation.py conclusiones preliminares en texto
│   └── tests/                    pytest, un archivo por módulo de spc/ y por router
├── web/
│   ├── app/                      (auth)/login, estudios, estudios/[id]/{datos,variables,atributos,supuestos,capacidad,diseno,muestreo,reporte}
│   ├── components/               gráficos Plotly, tablas, formularios, asistente de selección de gráfico
│   ├── lib/                      cliente Supabase, cliente API tipado, tipos generados
│   └── e2e/                      Playwright
├── supabase/migrations/          SQL versionado: tablas, RLS, índices
├── data/
│   ├── ejemplos/                 archivos sintéticos por tipo de gráfico (CSV y XLSX)
│   ├── referencia/               ejemplos de libro con resultado esperado, para validar
│   └── generar_ejemplos.py
└── docs/
    ├── PLAN.md                   copia de este plan
    ├── arquitectura.md, contrato-api.md, despliegue.md, ejecucion-agentes.md
    ├── fundamentos-estadisticos.md   fórmulas y fuente de cada cálculo
    ├── validacion.md             evidencia: resultado del software contra el del libro
    ├── empresa/                  guía de visita, formato de recolección, plan de muestreo
    ├── informe/                  informe técnico APA
    ├── manual/                   manual de usuario
    └── video/                    guion y storyboard
```

`test.py` contiene texto basura y se elimina.

### Modelo de datos (Supabase)

Todas las tablas llevan `user_id uuid default auth.uid()` y política RLS `user_id = auth.uid()` para select, insert, update y delete.

| Tabla | Contenido |
|---|---|
| `studies` | nombre, empresa, proceso, producto, característica, unidad, tipo (variable o atributo), LSL, USL, objetivo, notas |
| `datasets` | `study_id`, fase (I o II), columnas, definición de subgrupos, filas en JSONB, bitácora de limpieza |
| `control_limits` | `study_id`, tipo de gráfico, límites y parámetros congelados de Fase I, puntos excluidos con su causa asignable |
| `analyses` | `study_id`, módulo, parámetros, resultado JSONB, fecha (reproducibilidad y fuente del reporte) |
| `sampling_plans` | `study_id`, tipo de plan, AQL, LTPD, α, β, n, c, resultado |

## Alcance por módulo

| # | Módulo | Qué hace | Detalle que cuida la rúbrica |
|---|---|---|---|
| 1 | Datos | Carga CSV y XLSX, mapeo de columnas, subgrupos racionales (por columna, por tamaño fijo o por tiempo), limpieza con bitácora, tabla resumen | Los atípicos no se borran en silencio: se marcan y se justifica (ID3) |
| 2 | Variables | X̄-R, X̄-S, I-MR | **Fase I**: límites de prueba, exclusión de puntos con causa asignable documentada, recálculo, congelar. **Fase II**: datos nuevos contra límites congelados, sin recalcular |
| 3 | Atributos | p, np, c, u con n variable | Asistente que recomienda el gráfico según defectuosos o defectos y n constante o variable, con la justificación escrita |
| 4 | Supuestos | Normalidad (Shapiro-Wilk, Anderson-Darling, Q-Q, histograma); independencia (ACF con bandas, Ljung-Box, prueba de rachas); reglas Western Electric y Nelson configurables | En R, S y atributos con límites asimétricos solo se aplican las reglas válidas |
| 5 | Capacidad | Cp, Cpk, Cpl, Cpu, Pp, Ppk, intervalos de confianza, fracción no conforme esperada y observada, PPM | Advierte si el proceso no es estable o no es normal antes de interpretar |
| 6 | Diseño | ARL0, ARL1 y ATS exactos para Shewhart; simulación acotada cuando hay reglas suplementarias; curvas OC; tabla comparativa por n, L, intervalo h y desplazamiento δ | Incluye carga muestral (n/h) para conectar con la decisión de muestreo |
| 7 | Muestreo | Plan simple por atributos a partir de AQL, LTPD, α, β; curva OC, AOQ, AOQL, ATI; plan doble | Evaluar un plan existente (n, c) además de diseñarlo |
| 8 | Reportes | Página de reporte imprimible a PDF, exportación a Excel, descarga de gráficos PNG, conclusiones preliminares automáticas | Tablas y figuras numeradas y tituladas, listas para el informe APA |

Límites conocidos de Vercel que condicionan el diseño: el paquete Python no puede superar 250 MB (por eso sin pandas ni statsmodels; Ljung-Box y ACF se implementan con numpy) y las funciones tienen tiempo máximo (la simulación de ARL se vectoriza y se limita en réplicas).

## Agentes

Se crean en `.claude/agents/`. Cada uno es dueño de carpetas distintas, así pueden correr a la vez sin pisarse y sin worktrees. Ninguno edita `api/app/schemas/`: si necesita un cambio de contrato lo reporta y lo aplica la sesión principal.

| Agente | Modelo | Esfuerzo | Dueño de | Tarea |
|---|---|---|---|---|
| `spc-graficos` | opus | high | `spc/{constants,variables,attributes,phases,rules}.py` y sus tests | Gráficos de control, Fase I/II y reglas |
| `spc-analisis` | opus | high | `spc/{assumptions,capability,design,sampling,interpretation}.py` y sus tests | Supuestos, capacidad, ARL/ATS, muestreo |
| `backend-api` | sonnet | medium | `api/main.py`, `auth.py`, `routers/`, tests de routers | Endpoints, JWT, lectura de archivos, exportación Excel |
| `supabase-db` | sonnet | medium | `supabase/` | Migraciones, RLS, pruebas de aislamiento entre usuarios |
| `frontend-web` | sonnet | high | `web/` | Interfaz, login, gráficos, reporte imprimible |
| `datos-prueba` | haiku | low | `data/`, `docs/empresa/` | Datos sintéticos, casos de libro, formatos de recolección |
| `validador-estadistico` | opus | xhigh | `docs/validacion.md`, `docs/fundamentos-estadisticos.md` | Revisión independiente de fórmulas contra ejemplos de Montgomery; no corrige, reporta |
| `qa-e2e` | sonnet | medium | `web/e2e/` | Playwright sobre el flujo completo y la lista de verificación del enunciado |
| `redactor-docs` | sonnet | medium | `docs/informe`, `docs/manual`, `docs/video`, `README.md` | Informe APA, manual, guion |

Cada definición incluye: alcance, carpetas que puede tocar, contrato que debe respetar, criterio de terminado (pruebas en verde) y formato del reporte final.

## Ejecución por olas

**Ola 0 — Base (sesión principal, secuencial)**
1. `git init`, estructura de carpetas, `CLAUDE.md`, `docs/PLAN.md`, definiciones de agentes.
2. Esqueleto de `web/` (create-next-app, Tailwind, Plotly) y `api/` (FastAPI con `/health`).
3. Escribir el contrato completo en `api/app/schemas/` y generar tipos TypeScript y respuestas de ejemplo.
4. **Prueba de humo de despliegue**: subir a Vercel el `api` con numpy y scipy y un endpoint mínimo, para confirmar tamaño y tiempos antes de construir encima.

**Ola 1 — En paralelo (5 agentes)**: `spc-graficos`, `spc-analisis`, `supabase-db`, `frontend-web` (login, estudios, módulo de datos y pantallas contra respuestas de ejemplo), `datos-prueba`.

**Ola 2 — Integración (2 agentes)**: `backend-api` conecta routers con `spc/`; `frontend-web` cambia ejemplos por la API real y construye el reporte.

**Ola 3 — Calidad y documentos (3 agentes)**: `validador-estadistico`, `qa-e2e`, `redactor-docs`. Los hallazgos del validador vuelven a `spc-graficos` o `spc-analisis` para corrección.

**Ola 4 — Cierre (sesión principal)**: despliegue a producción, recorrido de la lista de verificación del enunciado, caso de ejemplo completo cargado, etiqueta de versión.

Al terminar cada ola la sesión principal corre todas las pruebas y revisa los reportes antes de lanzar la siguiente. `docs/ejecucion-agentes.md` documenta cómo lanzar cada ola y qué pedirle a cada agente.

## Despliegue

Pasos que requieren tu cuenta (los demás los hago yo y quedan en `docs/despliegue.md`):

1. **Supabase**: crear el proyecto y pasarme URL, anon key y cadena de conexión. Yo aplico migraciones con la CLI de Supabase.
2. **GitHub**: crear el repositorio vacío (o autorizarme a crearlo con `gh`).
3. **Vercel**: `vercel login`. Se crean dos proyectos desde el mismo repositorio: `cep-web` (raíz `web/`) y `cep-api` (raíz `api/`).

Variables de entorno:

| Proyecto | Variables |
|---|---|
| `cep-web` | `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `API_URL` |
| `cep-api` | `SUPABASE_URL` (para JWKS), `ALLOWED_ORIGINS` |

Ejecución local: `supabase start`, `uvicorn main:app --reload` en `api/`, `npm run dev` en `web/`. Las claves van en `.env.local`, fuera de git, con `.env.example` documentado.

## Verificación

- **Estadística**: `pytest` en `api/tests/` con casos de libro de `data/referencia/` (resultado esperado conocido) para cada gráfico, índice de capacidad, ARL y plan de muestreo. `docs/validacion.md` tabula software contra libro; sirve también como evidencia de ejecución.
- **API**: pruebas de routers con `TestClient`, incluido rechazo sin JWT.
- **Base de datos**: prueba de que el usuario A no lee ni modifica datos del usuario B.
- **Interfaz**: Playwright recorre login → crear estudio → cargar archivo → Fase I → congelar → Fase II → supuestos → capacidad → ARL → muestreo → reporte.
- **Despliegue**: el mismo recorrido contra la URL de producción.
- **Enunciado**: la lista de verificación de la sección 9 se revisa punto por punto en la Ola 4.

## Fuera del alcance del software

La visita a la empresa, la recolección de datos reales y la grabación del video las hace el equipo. El plan deja listos la guía de visita, el formato de recolección, el plan de muestreo y el guion; el informe se redacta con el caso de ejemplo y marca con claridad las secciones que deben reemplazarse con la empresa real.
