-- Faz 3: gölge tahmin işi (shadow.yml) ve tarihsel tabanın cuma senkronu pg_cron'dan (R132, R134).
--
-- NEDEN: gölge tahmin karar anından (salı/cuma 12:00 Londra) SONRA koşmalı; GitHub'ın `schedule`ı
-- güvenilmez (0003). Canlı `observe` akışı football-data'nın sonrası dönemidir: cuma kararından önce
-- tabanı bir kez daha tazelemek, bayat durum korumasının düşürdüğü tahmin sayısını azaltır (ücretsiz).
--
-- NE: izinli listeye `shadow.yml` eklenir (`create or replace` listeyi BAŞTAN yazar: 0008'in beş adı
-- da burada). `history-dispatch-friday` aynı `ops.dispatch_history()`i cuma 09:50 UTC'de çağırır.

create or replace function ops.dispatch_workflow(p_workflow text) returns bigint
language plpgsql
set search_path = ''
as $$
declare
  token text;
begin
  if p_workflow is null or not (p_workflow = any (array[
    'seal.yml', 'snapshot.yml', 'collect-daily.yml', 'collect-news.yml', 'history.yml',
    'shadow.yml'
  ])) then
    raise exception 'ops.dispatch_workflow: izinli listede olmayan workflow: %', p_workflow;
  end if;

  select decrypted_secret into token
  from vault.decrypted_secrets
  where name = 'github_seal_dispatch';

  if token is null or token = '' then
    raise exception 'ops.dispatch_workflow: Vault secret github_seal_dispatch yok — % tetiklenmedi',
      p_workflow;
  end if;

  return net.http_post(
    url := 'https://api.github.com/repos/popiliadam/football-edge/actions/workflows/'
           || p_workflow || '/dispatches',
    body := jsonb_build_object('ref', 'main'),
    headers := jsonb_build_object(
      'Accept', 'application/vnd.github+json',
      'Authorization', 'Bearer ' || token,
      'Content-Type', 'application/json',
      'User-Agent', 'football-edge-pg-cron',
      'X-GitHub-Api-Version', '2022-11-28'
    ),
    timeout_milliseconds := 10000
  );
end;
$$;

create or replace function ops.dispatch_shadow() returns bigint
language plpgsql
set search_path = ''
as $$
begin
  return ops.dispatch_workflow('shadow.yml');
end;
$$;

revoke all on function ops.dispatch_workflow(text) from public, anon, authenticated;
revoke all on function ops.dispatch_shadow() from public, anon, authenticated;

-- Salı ve cuma 12:35 UTC: 12:00 Londra yaz saatinde 11:00, kışın 12:00 UTC — ikisinden de sonra.
-- Dakika mühür (:00/:15/:30/:45) ve snapshot (:22) dakikalarının dışında.
select cron.schedule('shadow-dispatch', '35 12 * * 2,5', 'select ops.dispatch_shadow()');
-- Cuma 09:50 UTC: salı işinin ikizi (0008), cuma kararından önce.
select cron.schedule('history-dispatch-friday', '50 9 * * 5', 'select ops.dispatch_history()');
