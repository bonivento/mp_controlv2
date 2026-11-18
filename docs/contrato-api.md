# Contrato de la API

La fuente de verdad son los esquemas Pydantic de [`api/app/schemas/`](../api/app/schemas/). De ellos salen `api/openapi.json` y los tipos de `web/lib/api-types.ts`. Este documento es el índice; el detalle de cada campo está en el esquema y en `/api/docs` con el servidor local encendido.

## Rutas

Todas son `POST` con cuerpo JSON salvo que se indique. Todas exigen `Authorization: Bearer <JWT de Supabase>` salvo `/api/health`.

| Módulo | Ruta | Entrada | Salida | Esquema |
|---|---|---|---|---|
| — | `GET /api/health` | — | estado y versiones | — |
| 1 Datos | `/api/data/parse` | archivo (`multipart`, campo `file`) | `ParsedFile` | `data.py` |
| 1 Datos | `/api/data/summary` | `SummaryRequest` | `SummaryResponse` | `data.py` |
| 1 Datos | `/api/data/summary/attributes` | `AttributeSummaryRequest` | `AttributeSummaryResponse` | `data.py` |
| 2 Variables | `/api/charts/variables` | `VariablesChartRequest` | `ChartResponse` | `charts.py` |
| 3 Atributos | `/api/charts/attributes` | `AttributesChartRequest` | `ChartResponse` | `charts.py` |
| 3 Atributos | `/api/charts/attributes/recommend` | `RecommendRequest` | `RecommendResponse` | `charts.py` |
| 4 Supuestos | `/api/assumptions` | `AssumptionsRequest` | `AssumptionsResponse` | `assumptions.py` |
| 5 Capacidad | `/api/capability` | `CapabilityRequest` | `CapabilityResponse` | `capability.py` |
| 6 Diseño | `/api/design/arl` | `ArlRequest` | `ArlResponse` | `design.py` |
| 6 Diseño | `/api/design/compare` | `CompareRequest` | `CompareResponse` | `design.py` |
| 7 Muestreo | `/api/sampling/single/design` | `SingleDesignRequest` | `SinglePlanResponse` | `sampling.py` |
| 7 Muestreo | `/api/sampling/single/evaluate` | `SingleEvaluateRequest` | `SinglePlanResponse` | `sampling.py` |
| 7 Muestreo | `/api/sampling/double/evaluate` | `DoubleEvaluateRequest` | `DoublePlanResponse` | `sampling.py` |
| 8 Reportes | `/api/reports/excel` | `ExcelReportRequest` | archivo `.xlsx` | `reports.py` |
| Asistente | `GET /api/assistant/status` | — | `AssistantStatus` | `assistant.py` |
| Asistente | `/api/assistant/chat` | `AssistantRequest` | flujo `text/event-stream` | `assistant.py` |

### Asistente con IA

`/api/assistant/chat` no devuelve JSON sino un flujo de eventos (`delta`, `tool`, `done`, `error`), descrito en el docstring de `api/app/schemas/assistant.py`. La web envía en cada petición la conversación y el contexto de la pantalla (ficha del estudio, parámetros y resultado reducido; nunca las filas de datos); la API sigue sin estado. El contexto completo serializado no puede pasar de 60 KB (422). Antes de abrir el flujo la ruta puede responder 401, 403 (`forbidden`: invitado sin acceso), 422 o 503 (`assistant_unavailable`: sin credencial del proveedor). La respuesta lleva `Cache-Control: no-cache, no-transform`: sin esa cabecera el rewrite de Next comprime y entrega todo de golpe.

## Convenciones

- **Índices** base 0, en el orden en que llegaron los subgrupos.
- **Fracciones y probabilidades** entre 0 y 1, no en porcentaje.
- **Lo que no se puede calcular** va como `null`, nunca NaN ni infinito, y se explica en `interpretation.warnings`.
- **Toda respuesta de análisis** trae `interpretation` con `summary`, `findings` y `warnings` en español. Son las conclusiones preliminares del módulo 8.
- **Errores**: cuerpo `ErrorResponse` (`detail` en español, mostrable al usuario, y `code`). 401 sin sesión válida; 422 para datos inválidos o insuficientes.

## Fase I y Fase II

Los dos endpoints de gráficos sirven para ambas fases según el campo `phase`:

| | Fase I | Fase II |
|---|---|---|
| `limits` en la petición | `null` | obligatorio (los congelados) |
| `excluded` | puntos retirados, cada uno con su causa | no se usa |
| Qué hace la API | estima parámetros sin los excluidos y construye límites | compara contra los límites recibidos; no recalcula |
| `limits` en la respuesta | parámetros nuevos, listos para congelar | los mismos que llegaron |

`FrozenLimits.params` guarda parámetros del proceso (`mu` y `sigma`, o `p_bar`, `c_bar`, `u_bar`), no los límites ya calculados. Así los límites se pueden reconstruir en Fase II aunque cambie el tamaño de muestra.

## Paneles con menos puntos que subgrupos

El panel de rango móvil (MR) no tiene valor para la primera observación. En todo panel, `indices[k]` dice a qué subgrupo (base 0) corresponde `values[k]`, y los índices de `violations` y `excluded` son siempre de subgrupo, nunca de posición dentro de `values`. El frontend debe ubicar las señales con `indices`, sin suponer un desplazamiento fijo.

Cada panel informa además `rules_applied` y `rules_skipped` (con el motivo). En R, S, MR y en atributos con un límite truncado no se evalúan las reglas de zonas (WE2, WE3, N5 a N8).

## Forma de `datasets.subgrouping`

Columna JSONB que escribe el frontend al guardar un conjunto de datos:

| Clave | Valores |
|---|---|
| `method` | `column`, `fixed_size` o `time` |
| `layout` | `long` (una fila por observación), `wide` (una fila por subgrupo, columnas x1..xn) o `attribute` |
| `column`, `size`, `time_column`, `time_unit` | según `method` |
| `value_columns` | columnas de medición (variables) |
| `count_column`, `size_column`, `counting` | atributos; `counting` es `defectives` o `defects` |
| `justification` | por qué ese subgrupo es racional (obligatoria en la interfaz) |

## Cambios aplicados al cerrar la Ola 1

- `ChartSeries`: nuevos `indices`, `rules_applied`, `rules_skipped`.
- Peticiones de gráficos: Fase II con `excluded` no vacío se rechaza con 422.
- `ArlResponse.arl0_std_error`; `oc_curve` en simulación es la de la regla de un punto sola.
- `DoublePlanResponse.aoql_at`; `SingleDesignRequest.reference_plan`.

## Cómo cambiar el contrato

Solo lo hace la sesión principal:

1. Editar el esquema en `api/app/schemas/`.
2. Regenerar `api/openapi.json` (comando en `CLAUDE.md`).
3. `cd web && npm run gen:api`.
4. Actualizar la tabla de este documento si cambió una ruta.
5. Avisar a los agentes afectados (routers, fixtures del frontend, columnas JSONB).
