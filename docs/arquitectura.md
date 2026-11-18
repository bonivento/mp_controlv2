# Arquitectura

## Vista general

```
┌────────────┐      ┌──────────────────────────┐   supabase-js + JWT    ┌──────────────────────┐
│ Navegador  │ ───> │ web  (Next.js en Vercel) │ ─────────────────────> │ Supabase             │
└────────────┘      │  interfaz, sesión, datos │                        │  Auth + Postgres+RLS │
                    └────────────┬─────────────┘                        └──────────────────────┘
                                 │ /api/*  (rewrite, mismo origen)                 ▲
                                 ▼                                                 │ claves públicas
                    ┌──────────────────────────┐                                   │ (JWKS)
                    │ api  (FastAPI en Vercel) │ ──────────────────────────────────┘
                    │  cálculo, sin estado     │
                    └──────────────────────────┘
```

Tres piezas, cada una con una sola responsabilidad:

| Pieza | Responsabilidad | No hace |
|---|---|---|
| `web/` | Interfaz, sesión del usuario, leer y guardar en Supabase, dibujar gráficos | Ningún cálculo estadístico |
| `api/` | Todos los cálculos, lectura de archivos, exportación a Excel, textos de interpretación | No guarda nada ni consulta la base de datos |
| Supabase | Usuarios y datos, con seguridad por filas | Ninguna lógica de negocio |

## Por qué así

- **La API sin estado** se prueba con entradas y salidas, sin base de datos de por medio, y la librería `spc/` puede validarse contra ejemplos de libro de forma aislada. Además, cada resultado es reproducible: misma entrada, misma salida.
- **El frontend guarda directo en Supabase** porque las políticas RLS ya resuelven quién puede ver qué. Pasar cada lectura por la API duplicaría código sin añadir seguridad.
- **El rewrite `/api/*`** hace que el navegador vea un solo origen, así que no hay configuración de CORS.
- **Dos proyectos en Vercel** (uno por carpeta) mantienen separados el entorno de Node y el de Python, y cada uno se despliega solo cuando cambia su carpeta.

## Flujo de un análisis

Ejemplo con un gráfico X-barra-R en Fase I:

1. El usuario sube un archivo. `web` lo envía a `POST /api/data/parse` y recibe la tabla.
2. El usuario elige columnas y define subgrupos. `web` guarda el resultado en la tabla `datasets` con fase I.
3. `web` envía los subgrupos a `POST /api/charts/variables` con `phase: "I"`. La API devuelve paneles, señales, parámetros e interpretación.
4. El usuario excluye un punto escribiendo la causa asignable. `web` repite la llamada con `excluded`.
5. El usuario congela. `web` guarda el objeto `limits` de la respuesta en `control_limits` y el análisis completo en `analyses`.
6. En Fase II, `web` lee `control_limits`, lo envía junto con los datos nuevos y `phase: "II"`. La API compara y no recalcula.
7. La página de reporte lee `analyses` y arma el documento sin volver a calcular.

## Seguridad

- El navegador solo tiene la clave pública de Supabase. Lo que protege los datos son las políticas RLS: `user_id = auth.uid()` en todas las tablas.
- La API exige el JWT de la sesión en cada ruta salvo `/api/health` y lo verifica con las claves públicas del proyecto de Supabase. No recibe ni usa ninguna clave de servicio.
- Los archivos subidos se procesan en memoria y no se almacenan.
- El asistente con IA es la única parte de la API que llama a un servicio externo (la API de Anthropic, modelo Claude Opus 5.5). La clave vive solo en el proyecto `cep-api` de Vercel. Hacia ese servicio sale el contexto reducido de la pantalla (ficha del estudio, parámetros, resultados), no las filas de datos. Las cifras que da el asistente vienen de ese contexto o de herramientas que llaman a `api/app/spc/`. No hay cuota por usuario porque la API no tiene estado: el tope de gasto se fija en la cuenta del proveedor.

## Límites de la plataforma que condicionan el diseño

| Límite de Vercel | Consecuencia |
|---|---|
| Paquete Python de 250 MB como máximo | Sin pandas ni statsmodels; CSV con la biblioteca estándar; Ljung-Box y autocorrelación escritos con numpy |
| Tiempo máximo por función | La simulación de ARL es vectorizada y tiene tope de corridas y de longitud |
| Cuerpo de petición de unos 4.5 MB | Archivos de hasta 5 MB no caben con holgura: el límite efectivo de carga se fija en 4 MB y 20 000 filas |
| Respuestas largas en flujo | El asistente responde con `text/event-stream`; tiene presupuesto de tiempo (`ASSISTANT_TIME_BUDGET`) y tope de llamadas al modelo por petición |
| Sin disco persistente | La API no guarda nada; todo estado vive en Supabase |

## Estructura del código

Ver el árbol comentado en [PLAN.md](PLAN.md) y los dueños de cada carpeta en [../CLAUDE.md](../CLAUDE.md).
