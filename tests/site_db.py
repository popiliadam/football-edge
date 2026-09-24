"""`sitedb` testlerinin veritabanı düzeni (Faz 6 İz B tasarımı §4.4/2, §4.4/4, §4.4/5).

İki yer. (i) TAM SIRA, `postgres` veritabanında: 0001→0014 tek işlemde uygulanır, katalog okunur,
işlem GERİ ALINIR (`full_sequence`). (ii) DAVRANIŞ, şablonun kopyasında: `site_tpl` yalnız sitenin
kapanışındaki ve 0013'ün dokunduğu migration'larla kurulur, her modül (ve her kurcalama varyantı)
`CREATE DATABASE … TEMPLATE site_tpl` ile kendi kopyasını alır, sonunda `DROP … WITH (FORCE)`.
Append-only tablolar DELETE/TRUNCATE kabul etmez: temizlik veritabanı düzeyindedir, tetikleyici
ASLA kapatılmaz (`tests/test_site_harness_rules.py`).

Koruma: adres yerel (loopback) değilse ya da canlı adrese eşitse testler REDDEDİLİR; adres yoksa
yerelde SKIP, `CI=true` iken FAIL (B10). Hata metni adresi basmaz (parola taşır).
Migration bağlantısı her yerde `postgres` rolüyledir: 0013'ün `alter default privileges for role
postgres` satırı yalnız onun yarattığı nesnelere uygulanır.
"""

from __future__ import annotations

import os
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

REPO = Path(__file__).resolve().parent.parent
MIGRATIONS = REPO / "db/migrations"
SITE_TEST_VAR = "SITE_TEST_DATABASE" + "_URL"
LIVE_VAR = "DATABASE" + "_URL"
LOOPBACK = frozenset({"localhost", "127.0.0.1", "::1"})
TEMPLATE_DB = "site_tpl"
COPY_PREFIX = "site_t_"
# m3: iki liste de ADIYLA; `db/migrations/`teki her dosya tam olarak birinde olmalı
# (`tests/test_site_template_subset.py`). Bilinmeyen dosya sınıflandırma kararını zorlar.
TEMPLATE_MIGRATIONS = (
    "0001_init.sql",
    "0002_sources.sql",
    "0013_api_roles_lockdown.sql",
    "0014_site_read.sql",
)
SKIPPED_MIGRATIONS = (
    "0003_seal_dispatch.sql",
    "0004_workflow_dispatch.sql",
    "0005_collect_dispatch.sql",
    "0006_history.sql",
    "0007_holdout.sql",
    "0008_history_dispatch.sql",
    "0009_model_predictions.sql",
    "0010_holdout_phase.sql",
    "0011_shadow_dispatch.sql",
    "0012_jev_features.sql",
)
NO_SITE_DB = f"SKIP: site-db ({SITE_TEST_VAR} yok)"


def refusal(url: str, live: str) -> str | None:
    """Atılabilir olmayan hedefin nedeni; atılabilirse None. Metin adresi TAŞIMAZ."""
    try:
        host = conninfo_to_dict(url).get("host")
    except psycopg.ProgrammingError:
        return f"{SITE_TEST_VAR} ayrıştırılamadı — testler reddedildi"
    if host not in LOOPBACK:
        return f"{SITE_TEST_VAR} yerel bir kabı göstermiyor — append-only tablolara yazılmaz"
    if live and url == live:
        return f"{SITE_TEST_VAR} {LIVE_VAR}'e eşit — testler reddedildi"
    return None


def guarded_url() -> str:
    url = os.environ.get(SITE_TEST_VAR, "")
    if not url:
        if os.environ.get("CI") == "true":
            pytest.fail(f"{SITE_TEST_VAR} yok ve CI=true — site-db kapısı atlanamaz (B10)")
        pytest.skip(NO_SITE_DB)
    reason = refusal(url, os.environ.get(LIVE_VAR, ""))
    if reason is not None:
        pytest.fail(reason)
    return url


def apply(cur: psycopg.Cursor[Any], name: str) -> None:
    # Parametresiz execute çok ifadeli metni olduğu gibi gönderir; `%` ve `$$` yorumlanmaz.
    cur.execute((MIGRATIONS / name).read_text(encoding="utf-8").encode())


def _require_postgres(cur: psycopg.Cursor[Any]) -> None:
    cur.execute("SELECT current_user")
    user = (cur.fetchone() or ("?",))[0]
    if user != "postgres":
        pytest.fail(f"migration'lar postgres rolüyle uygulanmalı, bağlantı {user!r}")


def _admin(url: str) -> psycopg.Connection[Any]:
    return psycopg.connect(url, autocommit=True)


@pytest.fixture(scope="session")
def site_cluster() -> str:
    """Oturum başında bayat şablon ve kopyalar silinir, şablon yeniden kurulur (n2)."""
    url = guarded_url()
    with _admin(url) as admin, admin.cursor() as cur:
        _require_postgres(cur)
        cur.execute(
            "SELECT datname FROM pg_database WHERE datname = %s OR starts_with(datname, %s)",
            (TEMPLATE_DB, COPY_PREFIX),
        )
        for (name,) in cur.fetchall():
            cur.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(TEMPLATE_DB)))
    with psycopg.connect(make_conninfo(url, dbname=TEMPLATE_DB)) as conn, conn.cursor() as cur:
        _require_postgres(cur)
        for name in TEMPLATE_MIGRATIONS:
            apply(cur, name)
        become_reader_allowed(cur)
        conn.commit()
    return url


def become_reader_allowed(cur: psycopg.Cursor[Any]) -> None:
    """Testin `SET ROLE site_reader` diyebilmesi (yalnız test kümesinde, T0 ölçümü).

    CREATEROLE'lü süper olmayan `postgres` yarattığı role ADMIN taşır ama SET taşımayabilir
    (`createrole_self_grant`). Üyelik KÜME düzeyindedir ve yalnız bu atılabilir kapta verilir;
    0014 kimseye `site_reader` üyeliği vermez (metin testi).
    """
    cur.execute("SELECT pg_has_role(current_user, 'site_reader', 'SET')")
    if not (cur.fetchone() or (False,))[0]:
        cur.execute("GRANT site_reader TO postgres WITH INHERIT FALSE, SET TRUE")


@contextmanager
def template_copy(cluster: str) -> Iterator[str]:
    """Şablonun dosya düzeyinde kopyası (tetikleyici ateşlenmez); çıkışta silinir."""
    name = COPY_PREFIX + secrets.token_hex(6)
    with _admin(cluster) as admin:
        admin.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
                sql.Identifier(name), sql.Identifier(TEMPLATE_DB)
            )
        )
    try:
        yield make_conninfo(cluster, dbname=name)
    finally:
        with _admin(cluster) as admin:
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
            )


@pytest.fixture(scope="module")
def site_db(site_cluster: str) -> Iterator[str]:
    """Modül başına şablonun kopyası."""
    with template_copy(site_cluster) as url:
        yield url


@pytest.fixture
def site_db_each(site_cluster: str) -> Iterator[str]:
    """Test başına kopya: kırık bir zincir sonraki vakayı zehirlemesin."""
    with template_copy(site_cluster) as url:
        yield url


@pytest.fixture(scope="module")
def full_sequence(site_cluster: str) -> Iterator[psycopg.Cursor[Any]]:
    """(i): `postgres` veritabanında 0001→0014 tek işlemde; sonunda GERİ ALINIR.

    Kum havuzu kilidi: hedefte `odds_snapshots` varsa (migration'ları uygulanmış bir kap) hiçbir
    şey uygulanmadan kırmızı. Şablon (`site_cluster`) önce kurulur: açık işlemdeki commit'lenmemiş
    rol satırı öteki kurulumu kilitlerdi.
    """
    conn = psycopg.connect(site_cluster)
    try:
        with conn.cursor() as cur:
            _require_postgres(cur)
            cur.execute("SELECT to_regclass('public.odds_snapshots') IS NULL")
            if not (cur.fetchone() or (False,))[0]:
                pytest.fail("postgres veritabanı boş değil — tam sıra uygulanmadı")
            for path in sorted(MIGRATIONS.glob("[0-9][0-9][0-9][0-9]_*.sql")):
                apply(cur, path.name)
            yield cur
    finally:
        conn.rollback()
        conn.close()


@contextmanager
def as_reader(cur: psycopg.Cursor[Any]) -> Iterator[psycopg.Cursor[Any]]:
    """Geri alınan bir kayıt noktasında `site_reader` olarak sorgular."""
    cur.execute("SAVEPOINT as_reader")
    cur.execute("SET LOCAL ROLE site_reader")
    try:
        yield cur
    finally:
        cur.execute("ROLLBACK TO SAVEPOINT as_reader")
