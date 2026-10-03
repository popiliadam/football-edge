"""0016 METNİ: `site.public_floor`un `search_path`i sabitlenir. Her kapıda, DB'siz.

Supabase advisors, 0014 canlıya uygulanınca (2026-10-03) `function_search_path_mutable` WARN'ı
verdi. Gövde ad çözmez (sabit), risk pratikte yoktur; uyarı listesi temiz kalsın diye sabitlenir
(kullanıcı kararı, kullanıcı oturumu Adım 12). Yorumlar ayıklanır, yorumdaki kelime sayılmaz.
"""

from __future__ import annotations

from pathlib import Path

from tests.sql_text import statements

MIGRATION = Path(__file__).resolve().parent.parent / "db/migrations/0016_site_floor_search_path.sql"


def test_0016_only_pins_the_floor_search_path_within_a_bounded_lock_wait() -> None:
    assert statements(MIGRATION.read_text(encoding="utf-8")) == [
        "set lock_timeout = '5s'",
        "alter function site.public_floor() set search_path = ''",
        "reset lock_timeout",
    ]
