-- `site.public_floor`un `search_path`i sabitlenir. Supabase advisors, 0014 canlıya uygulandıktan sonra
-- (2026-10-03) `function_search_path_mutable` WARN'ı verdi. Gövde ad çözmez (yalnız sabit bir
-- `timestamptz`; `pg_catalog` boş yolda da örtük aranır), yani risk pratikte yoktur — uyarı listesi
-- temiz kalsın ve gerçek bir uyarı gürültüde kaybolmasın diye sabitlenir (kullanıcı kararı, kullanıcı
-- oturumu Adım 12). `site_reader`a LOGIN veren migration bu yüzden 0017'dir.

-- DEFERRED 18f'in biçimi (0014 ile aynı): `set … reset` her gönderim biçiminde bağlar.
set lock_timeout = '5s';

alter function site.public_floor() set search_path = '';

reset lock_timeout;
