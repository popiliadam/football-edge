-- `site_reader`a oturum açma hakkı (Faz 6 İz B §4.2, AK18; docs/HANDOFF.md §0.4 Adım 14). Parola BURADA
-- YOKTUR: kullanıcı istemci tarafında `\password site_reader` ile verir (SCRAM; düz metin loga düşmez) ve
-- asistan parolayı görmez. pg_net artık riski (LOGIN'li rol `net.http_post` atabilir, `net.http_request_queue`
-- yu okuyup yazabilir; `postgres` geri alamaz) kullanıcı tarafından kabul edildi (Adım 13, 2026-10-03).
-- Geri alma: `alter role site_reader nologin` + parola döndürme (docs/RUNBOOK.md).

-- DEFERRED 18f'in biçimi (0014 ile aynı): `set … reset` her gönderim biçiminde bağlar.
set lock_timeout = '5s';

alter role site_reader login;

reset lock_timeout;
