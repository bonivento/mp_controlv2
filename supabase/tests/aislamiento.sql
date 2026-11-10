-- Pruebas de aislamiento entre usuarios (RLS + integridad entre dueños).
--
-- Cómo correrlas: ver supabase/README.md. Cada comprobación lanza una excepción
-- si falla; si el script termina sin error, todas pasaron. Se ejecuta dentro de
-- una transacción que termina en ROLLBACK, así que no deja datos.
-- Requiere haber aplicado antes las migraciones (y en Postgres sin Supabase,
-- tests/00_stub_supabase.sql).

begin;

create schema t;
grant usage on schema t to anon, authenticated;

-- Sentencia INSERT válida por tabla para (usuario, estudio, dataset).
create function t.insert_sql(tbl text, uid uuid, sid uuid, did uuid) returns text
language sql immutable as $$
  select case tbl
    when 'studies' then format(
      $f$insert into public.studies (user_id, name, data_type) values (%L, 'x', 'variable')$f$, uid)
    when 'datasets' then format(
      $f$insert into public.datasets (user_id, study_id, name, phase, rows) values (%L, %L, 'x', 'I', '[]')$f$, uid, sid)
    when 'control_limits' then format(
      $f$insert into public.control_limits (user_id, study_id, dataset_id, chart_type, limits, is_active)
         values (%L, %L, %L, 'p', '{}', false)$f$, uid, sid, did)
    when 'analyses' then format(
      $f$insert into public.analyses (user_id, study_id, dataset_id, module, title, params, result)
         values (%L, %L, %L, 'data', 'x', '{}', '{}')$f$, uid, sid, did)
    when 'sampling_plans' then format(
      $f$insert into public.sampling_plans (user_id, study_id, name, plan_type, params, result)
         values (%L, %L, 'x', 'single', '{}', '{}')$f$, uid, sid)
  end
$$;
grant execute on function t.insert_sql(text, uuid, uuid, uuid) to anon, authenticated;

-- Ejecuta una sentencia y devuelve true si falló (con el mensaje al log).
create function t.fails(q text) returns boolean language plpgsql as $$
begin
  execute q;
  return false;
exception when others then
  return true;
end $$;
grant execute on function t.fails(text) to anon, authenticated;

create function t.rows_affected(q text) returns bigint language plpgsql as $$
declare n bigint;
begin
  execute q;
  get diagnostics n = row_count;
  return n;
end $$;
grant execute on function t.rows_affected(text) to anon, authenticated;

create function t.expect(cond boolean, msg text) returns void language plpgsql as $$
begin
  if not cond then raise exception 'FALLA: %', msg; end if;
  raise notice 'ok: %', msg;
end $$;
grant execute on function t.expect(boolean, text) to anon, authenticated;

-- Dos usuarios y una fila de cada tabla para B (como superusuario, sin RLS).
insert into auth.users (id, email) values
  ('aaaaaaaa-0000-0000-0000-000000000001', 'a@test'),
  ('bbbbbbbb-0000-0000-0000-000000000002', 'b@test');

insert into public.studies (id, user_id, name, data_type)
  values ('bbbbbbbb-1000-0000-0000-000000000001', 'bbbbbbbb-0000-0000-0000-000000000002', 'estudio de B', 'variable');
insert into public.datasets (id, user_id, study_id, name, phase, rows)
  values ('bbbbbbbb-2000-0000-0000-000000000001', 'bbbbbbbb-0000-0000-0000-000000000002',
          'bbbbbbbb-1000-0000-0000-000000000001', 'datos de B', 'I', '[]');
insert into public.control_limits (id, user_id, study_id, dataset_id, chart_type, limits)
  values ('bbbbbbbb-3000-0000-0000-000000000001', 'bbbbbbbb-0000-0000-0000-000000000002',
          'bbbbbbbb-1000-0000-0000-000000000001', 'bbbbbbbb-2000-0000-0000-000000000001', 'p', '{}');
insert into public.analyses (id, user_id, study_id, module, title, params, result)
  values ('bbbbbbbb-4000-0000-0000-000000000001', 'bbbbbbbb-0000-0000-0000-000000000002',
          'bbbbbbbb-1000-0000-0000-000000000001', 'data', 'análisis de B', '{}', '{}');
insert into public.sampling_plans (id, user_id, study_id, name, plan_type, params, result)
  values ('bbbbbbbb-5000-0000-0000-000000000001', 'bbbbbbbb-0000-0000-0000-000000000002',
          'bbbbbbbb-1000-0000-0000-000000000001', 'plan de B', 'single', '{}', '{}');

-- ---------------------------------------------------------------------------
-- Sesión de A (authenticated)
-- ---------------------------------------------------------------------------
select set_config('request.jwt.claims',
  '{"sub":"aaaaaaaa-0000-0000-0000-000000000001","role":"authenticated"}', true);
set local role authenticated;

do $$
declare
  tbl text;
  a   constant uuid := 'aaaaaaaa-0000-0000-0000-000000000001';
  b   constant uuid := 'bbbbbbbb-0000-0000-0000-000000000002';
  bs  constant uuid := 'bbbbbbbb-1000-0000-0000-000000000001';
  bd  constant uuid := 'bbbbbbbb-2000-0000-0000-000000000001';
  n   bigint;
begin
  perform t.expect(auth.uid() = a, 'auth.uid() es A');

  foreach tbl in array array['studies','datasets','control_limits','analyses','sampling_plans'] loop
    execute format('select count(*) from public.%I', tbl) into n;
    perform t.expect(n = 0, tbl || ': A no lee filas de B');

    perform t.expect(t.fails(t.insert_sql(tbl, b, bs, bd)),
      tbl || ': A no inserta a nombre de B');

    perform t.expect(
      t.rows_affected(format($q$update public.%I set user_id = user_id where id::text like 'bbbbbbbb-%%'$q$, tbl)) = 0,
      tbl || ': A no actualiza filas de B');

    perform t.expect(
      t.rows_affected(format($q$delete from public.%I where id::text like 'bbbbbbbb-%%'$q$, tbl)) = 0,
      tbl || ': A no borra filas de B');
  end loop;

  -- Intentar "regalar" o reclamar filas: A inserta con user_id propio pero
  -- apuntando al estudio de B (el hueco que la política sola no cierra).
  foreach tbl in array array['datasets','control_limits','analyses','sampling_plans'] loop
    perform t.expect(t.fails(t.insert_sql(tbl, a, bs, null)),
      tbl || ': A no inserta con user_id propio y study_id de B');
  end loop;
end $$;

-- A en su propio espacio: puede crear, y los vínculos deben ser coherentes.
insert into public.studies (id, name, data_type)   -- user_id por defecto = auth.uid()
  values ('aaaaaaaa-1000-0000-0000-000000000001', 'estudio de A', 'variable'),
         ('aaaaaaaa-1000-0000-0000-000000000002', 'otro estudio de A', 'variable');
insert into public.datasets (id, study_id, name, phase, rows)
  values ('aaaaaaaa-2000-0000-0000-000000000001', 'aaaaaaaa-1000-0000-0000-000000000001', 'datos de A', 'I', '[]');

do $$
declare
  a  constant uuid := 'aaaaaaaa-0000-0000-0000-000000000001';
  as1 constant uuid := 'aaaaaaaa-1000-0000-0000-000000000001';
  as2 constant uuid := 'aaaaaaaa-1000-0000-0000-000000000002';
  ad  constant uuid := 'aaaaaaaa-2000-0000-0000-000000000001';
  bd  constant uuid := 'bbbbbbbb-2000-0000-0000-000000000001';
  tbl text;
begin
  perform t.expect((select count(*) from public.studies) = 2, 'A ve solo sus 2 estudios');
  perform t.expect(not t.fails(t.insert_sql('analyses', a, as1, ad)), 'A inserta análisis con su dataset');
  perform t.expect(t.fails(t.insert_sql('analyses', a, as1, bd)), 'A no apunta a un dataset de B');
  perform t.expect(t.fails(t.insert_sql('analyses', a, as2, ad)),
    'dataset_id debe pertenecer al mismo estudio (otro estudio de A rechazado)');
  perform t.expect(t.fails(t.insert_sql('control_limits', a, as2, ad)),
    'control_limits: dataset de otro estudio rechazado');
  perform t.expect(t.fails($q$update public.datasets set study_id = 'bbbbbbbb-1000-0000-0000-000000000001'
                              where id = 'aaaaaaaa-2000-0000-0000-000000000001'$q$),
    'A no mueve su dataset al estudio de B');
  perform t.expect(t.fails($q$update public.studies set user_id = 'bbbbbbbb-0000-0000-0000-000000000002'
                              where id = 'aaaaaaaa-1000-0000-0000-000000000001'$q$),
    'A no traspasa su estudio a B');
  perform t.expect(t.fails($q$insert into public.studies (name, data_type, lsl, usl)
                              values ('x','variable', 5, 1)$q$), 'lsl < usl obligatorio');
  perform t.expect(t.fails($q$insert into public.datasets (study_id, name, phase, rows)
                              values ('aaaaaaaa-1000-0000-0000-000000000001','x','I','{}')$q$),
    'rows debe ser un arreglo JSON');

  -- Borrar el dataset deja el análisis con dataset_id nulo pero conserva study_id.
  delete from public.datasets where id = ad;
  perform t.expect(
    (select dataset_id is null and study_id = as1 from public.analyses where study_id = as1 limit 1),
    'borrar dataset anula dataset_id y conserva study_id');

  -- Borrar el estudio arrastra todo lo de A.
  delete from public.studies where id = as1;
  perform t.expect((select count(*) from public.analyses) = 0, 'borrar estudio borra sus análisis (cascada)');
end $$;

reset role;

-- B conserva intactas sus filas tras todo lo de A.
do $$
begin
  perform t.expect((select count(*) from public.studies where user_id = 'bbbbbbbb-0000-0000-0000-000000000002') = 1
    and (select count(*) from public.datasets where user_id = 'bbbbbbbb-0000-0000-0000-000000000002') = 1
    and (select count(*) from public.control_limits where user_id = 'bbbbbbbb-0000-0000-0000-000000000002') = 1
    and (select count(*) from public.analyses where user_id = 'bbbbbbbb-0000-0000-0000-000000000002') = 1
    and (select count(*) from public.sampling_plans where user_id = 'bbbbbbbb-0000-0000-0000-000000000002') = 1,
    'las filas de B siguen intactas');
end $$;

-- ---------------------------------------------------------------------------
-- Sesión de B: ve lo suyo y no lo de A
-- ---------------------------------------------------------------------------
select set_config('request.jwt.claims',
  '{"sub":"bbbbbbbb-0000-0000-0000-000000000002","role":"authenticated"}', true);
set local role authenticated;
do $$
declare tbl text; n bigint;
begin
  foreach tbl in array array['studies','datasets','control_limits','analyses','sampling_plans'] loop
    execute format('select count(*) from public.%I', tbl) into n;
    perform t.expect(n = 1, tbl || ': B ve exactamente su fila');
  end loop;
end $$;
reset role;

-- ---------------------------------------------------------------------------
-- Visitante sin sesión (anon): nada de nada
-- ---------------------------------------------------------------------------
select set_config('request.jwt.claims', '{"role":"anon"}', true);
set local role anon;
do $$
declare tbl text;
begin
  foreach tbl in array array['studies','datasets','control_limits','analyses','sampling_plans'] loop
    -- Sin privilegios la lectura falla; con ellos devolvería 0 filas. Ambos valen.
    perform t.expect(
      t.fails(format('select count(*) from public.%I', tbl))
      or t.rows_affected(format('select * from public.%I', tbl)) = 0,
      tbl || ': anon no ve filas');
    perform t.expect(
      t.fails(t.insert_sql(tbl, 'bbbbbbbb-0000-0000-0000-000000000002',
        'bbbbbbbb-1000-0000-0000-000000000001', null)),
      tbl || ': anon no inserta');
  end loop;
end $$;
reset role;

rollback;
