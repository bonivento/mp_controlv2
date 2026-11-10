-- Datos semilla SOLO PARA LOCAL (`supabase start` / `supabase db reset`).
-- No se ejecuta contra el proyecto remoto: `db push` no corre el seed.
--
-- Usuario de demostración:  demo@cep.local  /  demo-cep-2026
-- Estudio de ejemplo SINTÉTICO (is_synthetic = true).

insert into auth.users (
  instance_id, id, aud, role, email, encrypted_password, email_confirmed_at,
  raw_app_meta_data, raw_user_meta_data, created_at, updated_at,
  confirmation_token, recovery_token, email_change, email_change_token_new
) values (
  '00000000-0000-0000-0000-000000000000',
  '11111111-1111-1111-1111-111111111111',
  'authenticated', 'authenticated', 'demo@cep.local',
  extensions.crypt('demo-cep-2026', extensions.gen_salt('bf')), now(),
  '{"provider":"email","providers":["email"]}', '{}', now(), now(),
  '', '', '', ''
) on conflict (id) do nothing;

insert into auth.identities (
  id, user_id, provider_id, identity_data, provider,
  last_sign_in_at, created_at, updated_at
) values (
  '11111111-1111-1111-1111-111111111111',
  '11111111-1111-1111-1111-111111111111',
  '11111111-1111-1111-1111-111111111111',
  '{"sub":"11111111-1111-1111-1111-111111111111","email":"demo@cep.local","email_verified":true}',
  'email', now(), now(), now()
) on conflict do nothing;

insert into public.studies (
  id, user_id, name, company, process, product, characteristic, unit,
  data_type, lsl, usl, target, notes, is_synthetic
) values (
  '22222222-2222-2222-2222-222222222222',
  '11111111-1111-1111-1111-111111111111',
  'Ejemplo sintético: diámetro de eje', 'Empresa de ejemplo (sintética)',
  'Torneado', 'Eje de transmisión', 'Diámetro exterior', 'mm',
  'variable', 9.7, 10.3, 10.0,
  'DATOS SINTÉTICOS para demostración. No corresponden a ninguna empresa real.', true
) on conflict (id) do nothing;

insert into public.datasets (id, user_id, study_id, name, phase, source_file, subgrouping, rows)
values (
  '33333333-3333-3333-3333-333333333333',
  '11111111-1111-1111-1111-111111111111',
  '22222222-2222-2222-2222-222222222222',
  'Fase I (sintético)', 'I', 'ejemplo_sintetico_diametro.csv',
  '{"method":"fixed_size","size":5,"justification":"Cinco piezas consecutivas por hora: variación dentro del subgrupo solo por causas comunes."}',
  '[{"label":"1","values":[10.01,9.98,10.02,10.00,9.99]},
    {"label":"2","values":[10.03,10.00,9.97,10.01,10.02]},
    {"label":"3","values":[9.99,10.01,10.00,10.04,9.98]},
    {"label":"4","values":[10.00,10.02,9.99,10.01,10.00]},
    {"label":"5","values":[9.98,10.00,10.03,9.99,10.01]}]'
) on conflict (id) do nothing;
