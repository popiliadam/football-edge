"""0017 METNİ: `site_reader`a yalnız LOGIN verilir. Her kapıda, DB'siz.

Parola bu migration'da YOKTUR: kullanıcı istemci tarafında `\\password site_reader` ile verir
(SCRAM, AK18); asistan parolayı görmez. pg_net artık riski kullanıcı tarafından kabul edildi
(kullanıcı oturumu Adım 13, 2026-10-03). Yorumlar ayıklanır, yorumdaki kelime sayılmaz.
"""

from __future__ import annotations

from pathlib import Path

from tests.sql_text import statements

MIGRATION = Path(__file__).resolve().parent.parent / "db/migrations/0017_site_reader_login.sql"


def test_0017_only_grants_login_within_a_bounded_lock_wait() -> None:
    assert statements(MIGRATION.read_text(encoding="utf-8")) == [
        "set lock_timeout = '5s'",
        "alter role site_reader login",
        "reset lock_timeout",
    ]
