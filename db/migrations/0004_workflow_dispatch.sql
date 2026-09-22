-- Günlük snapshot turunu da GitHub'ın `schedule`ı yerine pg_cron'dan tetikle.
--
-- NEDEN: GitHub zamanlanmış workflow'ları geciktirir ve düşürür (bkz. 0003); `snapshot.yml`in
-- 06:17 turu saatlerce geç koşabiliyordu. 0003'ün mühür fonksiyonu tek bir dispatch
-- fonksiyonuna genelleşir; URL yalnız izinli listedeki bir addan kurulur.
--
-- TOKEN: 0003'teki Vault secret'ı `github_seal_dispatch` — adı yalnız mührü anıyor ama artık
-- İKİ workflow'a hizmet eder (seal.yml, snapshot.yml). Yeniden girilmesin diye adı aynı kaldı.
-- Canlıdaki `seal-dispatch` işinin komutu (`select ops.dispatch_seal()`) değişmeden çalışır.

create or replace function ops.dispatch_workflow(p_workflow text) returns bigint
language plpgsql
set search_path = ''
as $$
declare
  token text;
begin
  if p_workflow is null or not (p_workflow = any (array['seal.yml', 'snapshot.yml'])) then
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

create or replace function ops.dispatch_seal() returns bigint
language plpgsql
set search_path = ''
as $$
begin
  return ops.dispatch_workflow('seal.yml');
end;
$$;

create or replace function ops.dispatch_snapshot() returns bigint
language plpgsql
set search_path = ''
as $$
begin
  return ops.dispatch_workflow('snapshot.yml');
end;
$$;

-- Hiçbir API rolü çağıramaz: çağırabilseydi dışarıdan herkes Actions dakikası ve kredi yakardı.
revoke all on function ops.dispatch_workflow(text) from public, anon, authenticated;
revoke all on function ops.dispatch_seal() from public, anon, authenticated;
revoke all on function ops.dispatch_snapshot() from public, anon, authenticated;

-- :22, iki mühür dispatch'inin (:15, :30) ortası: aynı `odds-collect` grubunda bir mühür
-- turunun arkasında BEKLEYEN snapshot'ı, kuyruğa giren üçüncü bir tur sessizce iptal ettirir.
-- Aynı adla yeniden çalıştırmak işi GÜNCELLER (pg_cron ≥ 1.3), ikinci bir iş açmaz.
select cron.schedule('snapshot-dispatch', '22 6 * * *', 'select ops.dispatch_snapshot()');
