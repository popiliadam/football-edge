-- Mühür turlarını GitHub'ın `schedule`ı yerine pg_cron'dan tetikle.
--
-- NEDEN: GitHub zamanlanmış workflow'ları GARANTİ ETMEZ; yoğunlukta geciktirir ve düşürür.
-- 2026-09-19 11:20 → 09-21 14:15 arasında `seal.yml`in `*/15` cron'u ~203 tur yerine 16 tur
-- koştu (aralar 110–422 dk). Mühür penceresi 20 dk olduğu için bu 16 turun 15'i
-- `EXIT_MISSED_SEAL` verdi; loglardaki "kaçan mühür" listelerinin birleşimi 47 benzersiz maç.
-- O maçların kapanış fiyatı KALICI olarak kayıp.
--
-- NE: pg_cron dakika hassasiyetinde koşar; her 15 dakikada `ops.dispatch_seal()` pg_net ile
-- GitHub'ın `workflow_dispatch` API'sini çağırır. Mühür KODU değişmez: aynı `seal.yml`, aynı
-- secret'lar, aynı `odds-collect` concurrency grubu. `seal.yml`deki `schedule` YEDEK olarak
-- kalır — dispatch koparsa (ör. token süresi dolarsa) seyrek de olsa koşar ve kaçan mührü
-- kırmızıyla raporlar.
--
-- TOKEN depoya GİRMEZ: Supabase Vault'ta `github_seal_dispatch` adıyla durur (yalnız bu depoya
-- `Actions: Read and write` yetkili fine-grained PAT; kurulum ve yenileme docs/RUNBOOK.md).
-- Secret yoksa fonksiyon adıyla hata verir ve `cron.job_run_details` bunu gösterir.

create extension if not exists pg_cron with schema pg_catalog;
create extension if not exists pg_net with schema extensions;

create schema if not exists ops;
revoke all on schema ops from public;

create or replace function ops.dispatch_seal() returns bigint
language plpgsql
set search_path = ''
as $$
declare
  token text;
begin
  select decrypted_secret into token
  from vault.decrypted_secrets
  where name = 'github_seal_dispatch';

  if token is null or token = '' then
    raise exception 'ops.dispatch_seal: Vault secret github_seal_dispatch yok — seal.yml tetiklenmedi';
  end if;

  return net.http_post(
    url := 'https://api.github.com/repos/popiliadam/football-edge/actions/workflows/seal.yml/dispatches',
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

-- `ops` şeması API'ye açık değil; yine de savunma katmanı olarak hiçbir API rolü bu fonksiyonu
-- çağıramaz. Çağırabilseydi dışarıdan herkes Actions dakikası ve Odds API kredisi yakardı.
revoke all on function ops.dispatch_seal() from public, anon, authenticated;

-- Aynı adla yeniden çalıştırmak işi GÜNCELLER (pg_cron ≥ 1.3), ikinci bir iş açmaz.
select cron.schedule('seal-dispatch', '*/15 * * * *', 'select ops.dispatch_seal()');
