# Base de datos (Supabase)

Esquema, políticas RLS, pruebas de aislamiento y datos semilla del software CEP. El frontend usa `supabase-js` con la clave pública y el JWT del usuario: **toda la seguridad está en las políticas RLS** de estas migraciones. La clave `service_role` no se usa.

## Estructura

```
supabase/
  config.toml                  configuración local (puertos, auth, URLs)
  migrations/                  SQL versionado; nunca se edita una migración ya aplicada
  seed.sql                     usuario y estudio de demostración, SOLO local
  tests/aislamiento.sql        pruebas de RLS entre dos usuarios y visitante
  tests/00_stub_supabase.sql   imita auth.* para probar sin Docker (no aplicar en Supabase)
  tests/run-local.mjs          corre migraciones + pruebas en PGlite (Postgres en WASM)
```

## Modelo de seguridad

- Cada tabla tiene `user_id uuid default auth.uid()` y una política `*_owner` para el rol `authenticated`: `user_id = auth.uid()` en lectura y escritura.
- El rol `anon` (visitante sin sesión) no tiene privilegios ni política: no ve ni escribe nada.
- La política sola no impedía insertar una fila con `user_id` propio y `study_id` de otro usuario. La migración `20261110000000_endurecimiento.sql` lo cierra con claves foráneas compuestas `(study_id, user_id) -> studies (id, user_id)`; además `dataset_id` debe pertenecer al mismo `study_id`.

## Levantar en local (requiere Docker)

```bash
npx supabase start          # imprime API URL, clave anon y URL de Studio
npx supabase db reset       # recrea la base: migraciones + seed.sql
npx supabase stop
```

Valores para `web/.env.local`: `NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321` y `NEXT_PUBLIC_SUPABASE_ANON_KEY=<clave anon que imprime start>`. Studio: <http://127.0.0.1:54323>. Los correos de prueba llegan a Inbucket: <http://127.0.0.1:54324>.

Usuario de demostración (solo local): `demo@cep.local` / `demo-cep-2026`, con un estudio marcado `is_synthetic = true`.

## Crear una migración

```bash
npx supabase migration new nombre_del_cambio   # crea supabase/migrations/<fecha>_nombre_del_cambio.sql
# editar el SQL, luego:
npx supabase db reset                          # comprobar que todo corre desde cero
```

Reglas: nunca editar una migración ya aplicada; cambiar nombres de tablas o columnas obliga a avisar a `frontend-web`; toda tabla nueva lleva RLS habilitado, política por `user_id` y su caso en `tests/aislamiento.sql`.

## Pruebas de aislamiento

Con Docker:

```bash
npx supabase start
npx supabase db reset
psql "postgresql://postgres:postgres@127.0.0.1:54322/postgres" -v ON_ERROR_STOP=1 -f supabase/tests/aislamiento.sql
```

Sin Docker (PGlite; instalar una vez `npm i @electric-sql/pglite` en un directorio de trabajo y apuntar `NODE_PATH` a su `node_modules`):

```bash
NODE_PATH=<dir>/node_modules node supabase/tests/run-local.mjs --seed
```

El script termina con "TODAS LAS PRUEBAS PASARON" o lanza `FALLA: ...`. Termina en `ROLLBACK`, no deja datos. Nota: PGlite valida SQL y RLS, pero no reemplaza una prueba contra Supabase real (GoTrue, PostgREST, el JWT).

## Autenticación (correo y contraseña)

Configurada en `config.toml` para local; en el proyecto remoto se hace en el panel (*Authentication*):

| Ajuste | Local | Producción |
|---|---|---|
| Proveedor Email | activo | activo |
| Site URL | `http://localhost:3000` | URL de la web en Vercel (`https://<app>.vercel.app`) |
| Redirect URLs | `http://localhost:3000/**`, `http://127.0.0.1:3000/**` | añadir `https://<app>.vercel.app/**` (y el dominio propio si lo hay); conservar localhost para desarrollo |
| Confirmar correo | desactivado | recomendado activarlo; exige SMTP configurado (el servicio por defecto de Supabase tiene límite bajo de envíos) |
| Longitud mínima de contraseña | 8 | 8 |

Rutas: *Authentication > URL Configuration* para Site URL y Redirect URLs; *Authentication > Providers > Email* para la confirmación.

## Aplicar al proyecto remoto

```bash
npx supabase login
npx supabase link --project-ref <ref-del-proyecto>
npx supabase db push        # aplica migraciones pendientes; NO ejecuta seed.sql
```

Después fijar Site URL y Redirect URLs (sección anterior).

## Regenerar los tipos TypeScript

```bash
npx supabase gen types typescript --local > web/lib/database-types.ts                    # contra la base local
npx supabase gen types typescript --project-id <ref-del-proyecto> > web/lib/database-types.ts   # contra la remota
```

Regenerar cada vez que cambie una migración. El archivo actual fue escrito a mano con esa misma forma (no se pudo generar sin Docker); al regenerarlo con la CLI pueden cambiar detalles menores (por ejemplo `PostgrestVersion`).
