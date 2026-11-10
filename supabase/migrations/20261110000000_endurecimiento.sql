-- Endurecimiento del esquema inicial.
--
-- 1. Integridad entre dueños: la política RLS solo comprueba user_id = auth.uid(),
--    así que un usuario podía insertar un dataset (o análisis, límites, plan) con
--    user_id propio pero study_id de OTRO usuario. Se cierra con claves foráneas
--    compuestas (study_id, user_id) -> studies (id, user_id). Las comprobaciones
--    de claves foráneas no pasan por RLS, por lo que funcionan aunque el usuario
--    no pueda leer el estudio ajeno.
-- 2. dataset_id debe pertenecer al mismo estudio (clave compuesta con study_id).
-- 3. Formas mínimas de los JSONB y quitar privilegios a anon.

-- Objetivos de las claves compuestas.
alter table public.studies
  add constraint studies_id_user_key unique (id, user_id);
alter table public.datasets
  add constraint datasets_id_study_key unique (id, study_id);

-- Sustituyen (no se suman) a las claves simples, para que PostgREST no vea
-- dos relaciones entre las mismas tablas y no haya ambigüedad al incrustar.
alter table public.datasets drop constraint datasets_study_id_fkey;
alter table public.datasets
  add constraint datasets_study_owner_fkey
  foreign key (study_id, user_id) references public.studies (id, user_id) on delete cascade;

alter table public.control_limits drop constraint control_limits_study_id_fkey;
alter table public.control_limits drop constraint control_limits_dataset_id_fkey;
alter table public.control_limits
  add constraint control_limits_study_owner_fkey
  foreign key (study_id, user_id) references public.studies (id, user_id) on delete cascade;
alter table public.control_limits
  add constraint control_limits_dataset_study_fkey
  foreign key (dataset_id, study_id) references public.datasets (id, study_id)
  on delete set null (dataset_id);

alter table public.analyses drop constraint analyses_study_id_fkey;
alter table public.analyses drop constraint analyses_dataset_id_fkey;
alter table public.analyses
  add constraint analyses_study_owner_fkey
  foreign key (study_id, user_id) references public.studies (id, user_id) on delete cascade;
alter table public.analyses
  add constraint analyses_dataset_study_fkey
  foreign key (dataset_id, study_id) references public.datasets (id, study_id)
  on delete set null (dataset_id);

alter table public.sampling_plans drop constraint sampling_plans_study_id_fkey;
alter table public.sampling_plans
  add constraint sampling_plans_study_owner_fkey
  foreign key (study_id, user_id) references public.studies (id, user_id) on delete cascade;

-- Índices para las claves por dataset_id (borrado y consultas).
create index control_limits_dataset_idx on public.control_limits (dataset_id) where dataset_id is not null;
create index analyses_dataset_idx       on public.analyses (dataset_id) where dataset_id is not null;

-- Formas mínimas de los JSONB (el detalle lo valida la API).
alter table public.datasets
  add constraint datasets_rows_is_array check (jsonb_typeof(rows) = 'array'),
  add constraint datasets_subgrouping_is_object check (jsonb_typeof(subgrouping) = 'object'),
  add constraint datasets_cleaning_log_is_array check (jsonb_typeof(cleaning_log) = 'array'),
  add constraint datasets_name_not_blank check (length(trim(name)) > 0);
alter table public.control_limits
  add constraint control_limits_limits_is_object check (jsonb_typeof(limits) = 'object');
alter table public.analyses
  add constraint analyses_params_is_object check (jsonb_typeof(params) = 'object'),
  add constraint analyses_result_is_object check (jsonb_typeof(result) = 'object');
alter table public.sampling_plans
  add constraint sampling_plans_params_is_object check (jsonb_typeof(params) = 'object'),
  add constraint sampling_plans_result_is_object check (jsonb_typeof(result) = 'object');

-- El visitante sin sesión (rol anon) no necesita ningún privilegio: sin
-- política ya no vería filas, y así tampoco puede intentar escribir.
revoke all on public.studies, public.datasets, public.control_limits,
              public.analyses, public.sampling_plans from anon;
