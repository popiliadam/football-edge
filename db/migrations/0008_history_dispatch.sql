-- Faz 2 tarihsel tabanını (history.yml) pg_cron'dan haftalık tetikle.
--
-- NEDEN: football-data güncel sezon dosyalarını haftada iki kez günceller, ek lig dosyaları her
-- hafta büyür; tazelenmeyen taban T7 köprüsünü ve "sonrası" dönemini bayatlatır. GitHub'ın
-- `schedule`ı güvenilir değil (bkz. 0003).
--
-- NE: `ops.dispatch_workflow`un izinli listesine `history.yml` eklenir. `create or replace` listeyi
-- BAŞTAN yazar: 0005'in dört adı da burada durmalı, listeden düşen bir workflow'un cron işi her turda
-- hata verir.

create or replace function ops.dispatch_workflow(p_workflow text) returns bigint
language plpgsql
set search_path = ''
as $$
declare
  token text;
begin
  if p_workflow is null or not (p_workflow = any (array[
    'seal.yml', 'snapshot.yml', 'collect-daily.yml', 'collect-news.yml', 'history.yml'
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

create or replace function ops.dispatch_history() returns bigint
language plpgsql
set search_path = ''
as $$
begin
  return ops.dispatch_workflow('history.yml');
end;
$$;

-- Hiçbir API rolü çağıramaz: çağırabilseydi dışarıdan herkes Actions dakikası yakardı.
revoke all on function ops.dispatch_workflow(text) from public, anon, authenticated;
revoke all on function ops.dispatch_history() from public, anon, authenticated;

-- Salı 09:50 UTC: ana lig dosyaları pazartesi akşamı, ek lig dosyaları salı sabahı güncelleniyor
-- (Last-Modified 2026-09-21 17:50 ve 2026-09-22 08:10 GMT). Dakika mühür (:00/:15/:30/:45) ve
-- snapshot (:22) dakikalarının dışında. Aynı adla yeniden çalıştırmak işi GÜNCELLER.
select cron.schedule('history-dispatch', '50 9 * * 2', 'select ops.dispatch_history()');
