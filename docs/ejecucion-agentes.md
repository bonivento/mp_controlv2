# Cómo ejecutar el trabajo con los agentes

El trabajo se reparte entre nueve agentes definidos en [`.claude/agents/`](../.claude/agents/). Cada uno tiene su modelo, su nivel de esfuerzo y sus carpetas. Se lanzan por olas desde una sesión de Claude Code abierta en la raíz del proyecto: los de una misma ola corren a la vez; entre ola y ola la sesión principal revisa.

## Los agentes

| Agente | Modelo | Esfuerzo | Por qué ese nivel |
|---|---|---|---|
| `spc-graficos` | opus | alto | Fórmulas y reglas donde un error invalida el trabajo |
| `spc-analisis` | opus | alto | ARL, capacidad y muestreo exigen razonamiento estadístico cuidadoso |
| `validador-estadistico` | opus | muy alto | Es la última barrera antes del profesor; debe recalcular por caminos independientes |
| `frontend-web` | sonnet | alto | Mucho volumen de código y muchas pantallas, lógica convencional |
| `backend-api` | sonnet | medio | Capa delgada que une contrato y librería |
| `supabase-db` | sonnet | medio | Esquema pequeño; lo delicado son las políticas |
| `qa-e2e` | sonnet | medio | Pruebas de recorrido, trabajo metódico |
| `redactor-docs` | sonnet | medio | Redacción estructurada a partir de resultados ya obtenidos |
| `datos-prueba` | haiku | bajo | Generación mecánica de archivos |

## Por qué pueden trabajar en paralelo

1. **El contrato está escrito antes.** Los esquemas de `api/app/schemas/` fijan entradas y salidas, y la migración fija las tablas. El frontend programa contra eso con respuestas de ejemplo mientras la estadística se escribe.
2. **Cada agente tiene carpetas propias** (tabla en [`CLAUDE.md`](../CLAUDE.md)). Dos agentes nunca escriben el mismo archivo, así que no hacen falta ramas ni copias separadas del repositorio.
3. **Nadie cambia el contrato por su cuenta.** Quien necesita un cambio lo pide en su reporte y lo aplica la sesión principal.

## Olas

### Ola 0. Base (hecha)

Estructura, contrato, esquema de base de datos, esqueletos de `web/` y `api/`, agentes y documentación. Queda pendiente solo la prueba de humo del despliegue ([despliegue.md](despliegue.md), paso 3), que necesita la cuenta de Vercel.

### Ola 1. Construcción en paralelo: cinco agentes

Pedir a la sesión principal:

> Lanza la Ola 1: en un solo mensaje, los agentes `spc-graficos`, `spc-analisis`, `supabase-db`, `frontend-web` y `datos-prueba`, cada uno con el alcance de su definición.

Indicaciones propias de esta ola:

- `frontend-web`: acceso, estudios, módulo de datos y todas las pantallas de análisis en modo de ejemplo (`NEXT_PUBLIC_API_MOCK=1`).
- `spc-analisis` depende de `constants.py` y `rules.py` de `spc-graficos`; su definición ya dice cómo proceder mientras no existan.

**Revisión antes de seguir:**

- [ ] `cd api && .venv/bin/python -m pytest -q` pasa completo.
- [ ] `cd web && npm run lint && npm run build` sin errores.
- [ ] Las pruebas de aislamiento de `supabase/tests/` se ejecutaron (no solo se escribieron).
- [ ] Los archivos de `data/ejemplos/` abren.
- [ ] Cambios de contrato pedidos por los agentes: aplicados o descartados con motivo, y tipos regenerados.

### Ola 2. Integración: dos agentes

> Lanza la Ola 2: `backend-api` para reemplazar las rutas provisionales por los routers reales, y `frontend-web` para apagar el modo de ejemplo, conectar con la API real y construir la página de reporte.

Conviene que `backend-api` termine primero las rutas de datos y de gráficos, que son las que el frontend necesita antes.

**Revisión antes de seguir:**

- [ ] Pruebas de la API completas, incluidas las de routers.
- [ ] `api/openapi.json` regenerado sin diferencias.
- [ ] Recorrido manual en local: crear estudio, cargar `sintetico_fase1`, Fase I, congelar, Fase II con `sintetico_fase2`, reporte.

### Ola 3. Calidad y documentos: tres agentes

> Lanza la Ola 3: `validador-estadistico`, `qa-e2e` y `redactor-docs`.

`redactor-docs` usa `docs/fundamentos-estadisticos.md`, `docs/validacion.md` y `docs/capturas/`, que producen los otros dos. Si se lanzan a la vez, conviene que el redactor empiece por el manual y el guion y deje el informe para cuando los otros terminen; la alternativa es lanzarlo después.

Los hallazgos del validador se corrigen relanzando al dueño del archivo:

> Lanza `spc-graficos` para corregir estos hallazgos del validador: (pegar hallazgos). Después vuelve a lanzar `validador-estadistico` solo sobre esos puntos.

**Revisión antes de seguir:**

- [ ] Ningún hallazgo confirmado del validador queda abierto.
- [ ] Recorridos de Playwright en verde.
- [ ] Informe, manual y guion completos, con los bloques "por completar con la empresa" identificados.

### Ola 4. Cierre (sesión principal)

Despliegue a producción según [despliegue.md](despliegue.md), recorrido de la lista de verificación de la sección 9 del enunciado, carga del caso de ejemplo en producción y etiqueta de versión en git.

## Después: la empresa real

Cuando haya empresa y datos:

1. Llenar los formatos de `docs/empresa/` con la visita.
2. Cargar los datos reales en el software y repetir el análisis completo.
3. Relanzar `redactor-docs` indicando que reemplace los bloques por completar con la información real y sustituya el caso sintético por el real en el cuerpo del informe.
4. Grabar el video con el guion de `docs/video/guion.md`.

## Consejos de uso

- **Un agente no recuerda la conversación**: solo conoce su definición, `CLAUDE.md` y lo que se le diga al lanzarlo. Para una corrección hay que darle el hallazgo completo.
- **El reporte de un agente no es evidencia**: después de cada ola se corren las pruebas desde la sesión principal.
- **Para cambiar modelo o esfuerzo** de un agente se edita el encabezado de su archivo en `.claude/agents/` (`model` y `effort`).
- **Costo**: la Ola 1 lanza cinco agentes a la vez, dos de ellos con opus. Si se quiere gastar menos, se puede lanzar primero `spc-graficos` y `frontend-web` y el resto después.
