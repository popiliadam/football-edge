# Faz 6 İz B · B-1 T0 ölçümleri

Üreten: plan `docs/superpowers/plans/2026-09-24-faz6-iz-b-1-okuma-katmani.md` Task 0; tarih 2026-09-24T01:41Z.
Kap CI'ın kuracağı biçimde kuruldu (`postgres -D /etc/postgresql`, parola iş içinde üretildi; kap: izb-b1-site-t0).
Sonraki görevler aşağıdaki `anahtar=değer` satırlarını OKUR (tahmin etmez); testler eşitliği sınar.

```
image=public.ecr.aws/supabase/postgres:17.6.1.143
image_digest=sha256:80d7b27c3e8d77cfa7226eee9508671796da214781ff15a35b3670d7ad5ee453
server_version=17.6
ready_seconds=2
postgres_super_createdb_createrole_bypassrls=f,t,t,t
createrole_self_grant=bos
full_sequence_one_transaction=ok
full_sequence_seconds=1
cron_gone_after_rollback=t
postgres_db_empty_after_rollback=t
template_0001_0002_0013=ok
template_copy=ok
template_copy_tables=3
drop_database_force=ok
set_role=after_grant
netlify_cli=27.8.1
```
