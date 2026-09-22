-- Faz 1 toplayıcılarını da pg_cron'dan tetikle.
--
-- NEDEN: `fetch-*` komutları yalnız elle koşuyordu. Hiç koşmayan toplayıcı hiçbir şey toplamaz ve
-- kaçan bir gözlem, kapanış oranı gibi, sonradan üretilemez. GitHub'ın `schedule`ı da güvenilir
-- değil (bkz. 0003).
--
-- NE: `ops.dispatch_workflow`un izinli listesine `collect-daily.yml` ve `collect-news.yml` eklenir;
-- imza, token ve davranış 0004'le aynı. `create or replace` listeyi BAŞTAN yazar: 0004'teki adlar
-- burada da durmalı, listeden düşen bir workflow'un cron işi her turda hata verir.
-- Token aynı Vault secret'ı (`github_seal_dispatch`): adı yalnız mührü anar, izinli listedeki her
-- workflow'a hizmet eder.

create or replace function ops.dispatch_workflow(p_workflow text) returns bigint
language plpgsql
set search_path = ''
as $$
declare
  token text;
begin
  if p_workflow is null or not (p_workflow = any (array[
    'seal.yml', 'snapshot.yml', 'collect-daily.yml', 'collect-news.yml'
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

create or replace function ops.dispatch_collect_daily() returns bigint
language plpgsql
set search_path = ''
as $$
begin
  return ops.dispatch_workflow('collect-daily.yml');
end;
$$;

create or replace function ops.dispatch_collect_news() returns bigint
language plpgsql
set search_path = ''
as $$
begin
  return ops.dispatch_workflow('collect-news.yml');
end;
$$;

-- Hiçbir API rolü çağıramaz: çağırabilseydi dışarıdan herkes Actions dakikası yakardı.
revoke all on function ops.dispatch_workflow(text) from public, anon, authenticated;
revoke all on function ops.dispatch_collect_daily() from public, anon, authenticated;
revoke all on function ops.dispatch_collect_news() from public, anon, authenticated;

-- Günlük tur, günün snapshot turundan sonra: `fetch-venues` havayı `matches`teki yaklaşan maçlar
-- için çeker. Haber iki saatte bir. İki dakika da mühür dispatch'lerinin (:00/:15/:30/:45) dışında:
-- zaman-kritik mühür tetiği başka bir işle aynı dakikada kuyruğa girmez.
-- Aynı adla yeniden çalıştırmak işi GÜNCELLER (pg_cron ≥ 1.3), ikinci bir iş açmaz.
select cron.schedule('collect-daily-dispatch', '10 7 * * *', 'select ops.dispatch_collect_daily()');
select cron.schedule('collect-news-dispatch', '7 */2 * * *', 'select ops.dispatch_collect_news()');
