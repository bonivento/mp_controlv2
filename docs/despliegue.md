# Despliegue y ejecución

El software tiene tres partes: la base de datos en Supabase, la API en Vercel y la web en Vercel. Se despliegan en ese orden, porque cada una necesita datos de la anterior.

## Requisitos en la máquina

| Herramienta | Versión | Para qué | Estado en esta máquina (2026-11-09) |
|---|---|---|---|
| Node.js | 20 o superior | web y CLIs | instalado (26) |
| uv | cualquiera reciente | Python 3.12 y dependencias de la API | instalado |
| git | cualquiera | control de versiones | instalado |
| Docker Desktop | cualquiera | Supabase local (opcional) | sin comprobar |
| CLI de Supabase | — | migraciones | se usa con `npx supabase` |
| CLI de Vercel | — | despliegue | se usa con `npx vercel` |
| CLI de GitHub (`gh`) | — | crear el repositorio (opcional) | no instalado |

## Ejecución local

```bash
# 1. Base de datos local (requiere Docker). Imprime la URL y la clave pública.
npx supabase start

# 2. API en http://localhost:8000  (documentación en /api/docs)
cd api
uv venv --python 3.12 .venv && uv pip install -r requirements-dev.txt
AUTH_DISABLED=1 .venv/bin/uvicorn main:app --reload --port 8000

# 3. Web en http://localhost:3000
cd web
cp .env.example .env.local      # completar con los valores del paso 1
npm install
npm run dev
```

Sin Docker se puede trabajar contra el proyecto remoto de Supabase poniendo su URL y su clave pública en `web/.env.local`.

## Variables de entorno

| Dónde | Variable | Valor |
|---|---|---|
| web | `NEXT_PUBLIC_SUPABASE_URL` | URL del proyecto de Supabase |
| web | `NEXT_PUBLIC_SUPABASE_ANON_KEY` | clave pública (anon o publishable) |
| web | `API_URL` | URL del proyecto `cep-api`; en local `http://localhost:8000` |
| web | `NEXT_PUBLIC_API_MOCK` | `1` solo durante el desarrollo sin API |
| api | `SUPABASE_URL` | URL del proyecto, para descargar las claves públicas del JWT |
| api | `AUTH_DISABLED` | `1` solo en local; nunca en Vercel |

La clave `service_role` de Supabase no se usa en ninguna parte y no debe copiarse a Vercel.

## Paso 1. Supabase

1. Crear un proyecto en <https://supabase.com/dashboard> (región más cercana; guardar la contraseña de la base de datos).
2. En *Project Settings → API*, copiar la URL y la clave pública.
3. Aplicar las migraciones:
   ```bash
   npx supabase login
   npx supabase link --project-ref <ref-del-proyecto>
   npx supabase db push
   ```
4. En *Authentication → URL Configuration*, poner como *Site URL* la URL de producción de la web y añadir `http://localhost:3000` a las de redirección.
5. Comprobar en *Table Editor* que las cinco tablas existen y tienen RLS activo.

## Paso 2. Repositorio

```bash
git add -A && git commit -m "Base del proyecto"
git remote add origin git@github.com:<usuario>/<repositorio>.git
git push -u origin main
```

## Paso 3. API en Vercel

1. En Vercel, *Add New → Project*, importar el repositorio.
2. Nombre `cep-api`. **Root Directory: `api`**. Vercel detecta FastAPI por `main.py` y `requirements.txt`.
3. Añadir la variable `SUPABASE_URL`.
4. Desplegar y abrir `https://<cep-api>/api/health`. Debe responder `{"status": "ok", ...}` con las versiones de numpy y scipy.

Esta es la **prueba de humo**: se hace con la API todavía vacía para confirmar, antes de construir encima, que numpy y scipy caben en el límite de 250 MB y que el arranque en frío es aceptable. Si falla por tamaño, la salida es fijar versiones más livianas o excluir archivos de prueba de los paquetes con `excludeFiles` en `vercel.json`.

## Paso 4. Web en Vercel

1. *Add New → Project* otra vez con el mismo repositorio.
2. Nombre `cep-web`. **Root Directory: `web`**. Framework: Next.js.
3. Añadir `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` y `API_URL` (la URL de `cep-api`, sin barra final).
4. Desplegar. Volver al paso 1.4 y poner la URL definitiva como *Site URL*.

A partir de aquí cada `git push` a `main` despliega solo el proyecto cuya carpeta cambió.

## Comprobación después de desplegar

1. `https://<cep-api>/api/health` responde ok.
2. `https://<cep-web>/api/health` responde lo mismo (prueba el rewrite).
3. Registrar un usuario, crear un estudio, cargar `data/ejemplos/sintetico_fase1.csv` y obtener el gráfico.
4. Con un segundo usuario, comprobar que no ve el estudio del primero.
5. Correr las pruebas de extremo a extremo contra producción: `cd web && BASE_URL=https://<cep-web> npx playwright test`.

## Problemas conocidos

| Síntoma | Causa probable | Solución |
|---|---|---|
| El despliegue de la API falla por tamaño | Dependencia pesada añadida | Revisar `requirements.txt`; no pandas ni statsmodels |
| 401 en todas las llamadas | `SUPABASE_URL` mal puesta en `cep-api`, o sesión vencida | Corregir la variable y volver a desplegar; cerrar y abrir sesión |
| 404 en `/api/...` desde la web | `API_URL` vacía o con barra final | Corregir y volver a desplegar la web |
| La tabla sale vacía con sesión iniciada | Fila creada sin `user_id` o política RLS ausente | Revisar la migración y las pruebas de `supabase/tests/` |
| El correo de confirmación lleva a localhost | *Site URL* sin actualizar | Paso 1.4 |
| Tiempo agotado en ARL con reglas | Simulación demasiado larga | Bajar `max_runs` o `max_length` |
