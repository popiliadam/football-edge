-- Faz 3: faz başına en çok bir holdout açılışı (Faz 3 tasarımı §8.3, R135).
--
-- `final_eval` açmadan önce `holdout_access_log`u sayar; bu indeks ikinci katmandır. Amaç
-- `<faz>:<ön kayıt sha256>` ya da `<faz>-rerun:<neden>:<sha256>` biçimindedir; ilk parçası (faz ya
-- da faz-rerun) tekildir: ikinci bir `faz3` açılışı ve ikinci bir `faz3-rerun` INSERT'te düşer.
-- Faz 2'nin biçimsiz amaçları (yok — sayım 0) ve başka amaçlar kapsam dışıdır. Tablo değişmez
-- (satır tetikleyicileri 0007'de): yalnız bir ifade indeksi eklenir.

create unique index if not exists holdout_access_log_one_per_phase
  on holdout_access_log ((split_part(purpose, ':', 1)))
  where purpose ~ '^faz[0-9]+(-rerun)?:';
