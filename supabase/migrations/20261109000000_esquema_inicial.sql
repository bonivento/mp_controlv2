-- Esquema inicial del software CEP.
--
-- Principio: cada fila pertenece a un usuario (user_id) y las políticas RLS
-- garantizan que solo su dueño la lee o la modifica. El frontend accede con la
-- clave pública (anon) y el JWT del usuario; no existe clave de servicio en el
-- navegador.
--
-- Los resultados de análisis se guardan como JSONB con la misma forma que
-- devuelve la API (ver api/app/schemas/), para poder reconstruir el reporte
-- sin recalcular.

-- ---------------------------------------------------------------------------
-- Estudios: un proceso, una característica de calidad
-- ---------------------------------------------------------------------------
create table public.studies (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null default auth.uid() references auth.users (id) on delete cascade,
  name            text not null check (length(trim(name)) > 0),
  company         text,
  process         text,
  product         text,
  characteristic  text,
  unit            text,
  data_type       text not null check (data_type in ('variable', 'attribute')),
  lsl             double precision,
  usl             double precision,
  target          double precision,
  notes           text,
  is_synthetic    boolean not null default false,  -- true en los casos de ejemplo
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  check (lsl is null or usl is null or lsl < usl)
);

-- ---------------------------------------------------------------------------
-- Conjuntos de datos: lo que se cargó, ya organizado en subgrupos
-- ---------------------------------------------------------------------------
create table public.datasets (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null default auth.uid() references auth.users (id) on delete cascade,
  study_id      uuid not null references public.studies (id) on delete cascade,
  name          text not null,
  phase         text not null check (phase in ('I', 'II')),
  source_file   text,                       -- nombre del archivo original
  -- Definición de subgrupos racionales:
  -- {"method": "column" | "fixed_size" | "time", "column": "...", "size": 5, "justification": "..."}
  subgrouping   jsonb not null default '{}'::jsonb,
  -- Variables: [{"label": "1", "values": [..]}]
  -- Atributos: [{"label": "1", "count": 3, "size": 100}]
  rows          jsonb not null,
  -- Bitácora de limpieza: [{"action": "...", "detail": "...", "at": "..."}]
  cleaning_log  jsonb not null default '[]'::jsonb,
  created_at    timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Límites de control congelados al cerrar la Fase I
-- ---------------------------------------------------------------------------
create table public.control_limits (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null default auth.uid() references auth.users (id) on delete cascade,
  study_id     uuid not null references public.studies (id) on delete cascade,
  dataset_id   uuid references public.datasets (id) on delete set null,
  chart_type   text not null check (chart_type in ('xbar_r', 'xbar_s', 'i_mr', 'p', 'np', 'c', 'u')),
  limits       jsonb not null,              -- objeto FrozenLimits de la API
  is_active    boolean not null default true,
  created_at   timestamptz not null default now()
);

-- Un solo juego de límites vigente por estudio y tipo de gráfico.
create unique index control_limits_one_active
  on public.control_limits (study_id, chart_type)
  where is_active;

-- ---------------------------------------------------------------------------
-- Análisis guardados: fuente del reporte y evidencia de reproducibilidad
-- ---------------------------------------------------------------------------
create table public.analyses (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users (id) on delete cascade,
  study_id    uuid not null references public.studies (id) on delete cascade,
  dataset_id  uuid references public.datasets (id) on delete set null,
  module      text not null check (module in
                ('data', 'variables', 'attributes', 'assumptions', 'capability', 'design', 'sampling')),
  title       text not null,
  params      jsonb not null,               -- petición enviada a la API
  result      jsonb not null,               -- respuesta de la API
  in_report   boolean not null default true,
  created_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Planes de muestreo de aceptación
-- ---------------------------------------------------------------------------
create table public.sampling_plans (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users (id) on delete cascade,
  study_id    uuid not null references public.studies (id) on delete cascade,
  name        text not null,
  plan_type   text not null check (plan_type in ('single', 'double')),
  params      jsonb not null,
  result      jsonb not null,
  created_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Índices
-- ---------------------------------------------------------------------------
create index studies_user_idx         on public.studies (user_id, created_at desc);
create index datasets_study_idx       on public.datasets (study_id, created_at);
create index control_limits_study_idx on public.control_limits (study_id);
create index analyses_study_idx       on public.analyses (study_id, created_at);
create index sampling_plans_study_idx on public.sampling_plans (study_id);

-- ---------------------------------------------------------------------------
-- updated_at automático en studies
-- ---------------------------------------------------------------------------
create function public.set_updated_at() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

create trigger studies_set_updated_at
  before update on public.studies
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- Seguridad por filas: cada usuario solo ve y modifica lo suyo
-- ---------------------------------------------------------------------------
do $$
declare
  t text;
begin
  foreach t in array array['studies', 'datasets', 'control_limits', 'analyses', 'sampling_plans']
  loop
    execute format('alter table public.%I enable row level security', t);
    execute format(
      'create policy %I on public.%I for all to authenticated
         using (user_id = (select auth.uid()))
         with check (user_id = (select auth.uid()))',
      t || '_owner', t);
  end loop;
end;
$$;
