"""Uçtan uca (§4.4/3): gerçek görünüm SQL'i → dışa aktarıcı → `verify-snapshot`, kapta.

Beklenen değerler ELLE hesaplandı; türetme kodu çağrılmaz (adil kitaplar, `site_builders`).
Kurcalama iki varyant: çıpa ÖNCESİ ve SONRASI bir satırın fiyatı INSERT'ten ÖNCE değiştirilir,
saklanan hash'ler eski kalır — UPDATE ve tetikleyici kapatma yoktur. Her varyant kendi kopyasında.
Kimliklerde BOŞLUK vardır (canlı defter gibi): satır sayısı son kimliğe eşit değildir.
Sınır: `site.record` Faz 5'e kadar `where false`; sicil yalnız BOŞ hâliyle koşar (§12.4/12).
Başarılı koşu anlık görüntüyü `SITE_E2E_DIR`e (verify.sh `site-db` adımı) bu koşunun kimliğiyle
bırakır; B-2'nin `next build` adımı onu okur.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
import pytest

from football_edge.site.contract import DEVIG_CONFIG_PATH, EXIT_SITE_CHAIN
from football_edge.site.export import ExportRefused, devig_method, run_export
from tests.site_builders import (
    AWAY_FAVOURED,
    DRAWISH,
    EVEN,
    HOME_HEAVY,
    SYMMETRIC,
    Round,
    anchored_repo,
    ledger,
    payloads,
)
from tests.site_db import site_cluster, site_db_each

pytestmark = pytest.mark.sitedb

REPO = Path(__file__).resolve().parent.parent
SCHEMA: dict[str, Any] = json.loads(
    (REPO / "web/contract/snapshot.schema.json").read_text(encoding="utf-8")
)
M1, M2, M3 = ("01" + "ef" * 15), ("02" + "ef" * 15), ("03" + "ef" * 15)
EDGE, HOLDOUT, ASLEEP = ("04" + "ef" * 15), ("05" + "ef" * 15), ("06" + "ef" * 15)
MATCHES = [
    (M1, "e2e.1", "2026-09-22T14:00:00Z", "Alfa Spor", "Beta FK"),
    (M2, "e2e.1", "2026-09-23T15:00:00Z", "Gamma United", "Alfa Spor"),
    (M3, "e2e.1", "2026-09-24T16:00:00Z", "Delta Şehir", "Beta FK"),
    (EDGE, "e2e.1", "2026-07-01T23:59:59.999999Z", "Kenar A", "Kenar B"),
    (HOLDOUT, "e2e.1", "2026-01-15T12:00:00Z", "Eski A", "Eski B"),
    (ASLEEP, "e2e.9", "2026-09-21T18:00:00Z", "Uyku A", "Uyku B"),
]
ROUNDS = [
    Round(HOLDOUT, "2026-01-14T10:00:00Z", "Eski A", "Eski B", [EVEN] * 3),  # satır 1–9
    Round(EDGE, "2026-06-30T10:00:00Z", "Kenar A", "Kenar B", [EVEN] * 3),  # 10–18
    Round(M1, "2026-09-20T10:00:00Z", "Alfa Spor", "Beta FK", [EVEN] * 3),  # 19–27
    Round(ASLEEP, "2026-09-20T09:00:00Z", "Uyku A", "Uyku B", [EVEN] * 3),  # 28–36
    Round(M2, "2026-09-20T11:00:00Z", "Gamma United", "Alfa Spor", [AWAY_FAVOURED] * 3),  # 37–45
    Round(M1, "2026-09-21T10:00:00Z", "Alfa Spor", "Beta FK", [EVEN] * 3, drop_away_for=0),  # 46–53
    Round(M2, "2026-09-21T11:00:00Z", "Gamma United", "Alfa Spor", [DRAWISH] * 3),  # 54–62
    Round(M3, "2026-09-21T12:00:00Z", "Delta Şehir", "Beta FK", [HOME_HEAVY] * 2),  # 63–68
    Round(M1, "2026-09-22T13:00:00Z", "Alfa Spor", "Beta FK", SYMMETRIC, is_closing=True),  # 69–77
]
ROWS = ledger(payloads(ROUNDS))
# Canlı defterin kimliklerinde boşluk var (5763 satır, last_id 6165): geri alınan bir yazım sıra
# değerlerini geri vermez. Tohum aynısını yapar — satır sırası → önünde geri alınan toplu yazımın
# yaktığı kimlik sayısı. Kimlikler ELLE: 1–10, (11–14 yandı) 15–54, (55–57 yandı) 58–84.
BURNED = {10: 4, 50: 3}
IDS = (*range(1, 11), *range(15, 55), *range(58, 85))
ANCHOR_ROWS = 40  # kesimin ortası: öncesi ve sonrası satır var; çıpanın last_id'si 44
CLOSE = {
    "observed_at": "2026-09-22T13:00:00Z",
    "books": 3,
    "p": {"home": 33.3, "draw": 33.3, "away": 33.3},
}
EXPECTED_MATCHES = [
    {
        "id": M1,
        "league_id": "e2e.1",
        "path_id": M1[:12],
        "slug": "alfa-spor-vs-beta-fk",
        "date": "2026-09-22",
        "commence_time": "2026-09-22T14:00:00Z",
        "home": "Alfa Spor",
        "away": "Beta FK",
        "sealed": True,
        "rounds": 3,
        "h2h": {
            "opening": {
                "observed_at": "2026-09-20T10:00:00Z",
                "books": 3,
                "p": {"home": 50.0, "draw": 25.0, "away": 25.0},
            },
            "latest": CLOSE,
            "closing": CLOSE,
        },
        "move": {"home": -16.7, "draw": 8.3, "away": 8.3},
        "indexable": True,
    },
    {
        "id": M2,
        "league_id": "e2e.1",
        "path_id": M2[:12],
        "slug": "gamma-united-vs-alfa-spor",
        "date": "2026-09-23",
        "commence_time": "2026-09-23T15:00:00Z",
        "home": "Gamma United",
        "away": "Alfa Spor",
        "sealed": False,
        "rounds": 2,
        "h2h": {
            "opening": {
                "observed_at": "2026-09-20T11:00:00Z",
                "books": 3,
                "p": {"home": 25.0, "draw": 25.0, "away": 50.0},
            },
            "latest": {
                "observed_at": "2026-09-21T11:00:00Z",
                "books": 3,
                "p": {"home": 20.0, "draw": 40.0, "away": 40.0},
            },
            "closing": None,
        },
        "move": {"home": -5.0, "draw": 15.0, "away": -10.0},
        "indexable": True,
    },
    {
        "id": M3,
        "league_id": "e2e.1",
        "path_id": M3[:12],
        "slug": "delta-sehir-vs-beta-fk",
        "date": "2026-09-24",
        "commence_time": "2026-09-24T16:00:00Z",
        "home": "Delta Şehir",
        "away": "Beta FK",
        "sealed": False,
        "rounds": 1,
        "h2h": {"opening": None, "latest": None, "closing": None},
        "move": None,
        "indexable": False,
    },
]
COLUMNS = (
    "match_id",
    "observed_at",
    "bookmaker",
    "market",
    "outcome",
    "point",
    "price",
    "bookmaker_last_update",
    "is_closing",
    "prev_hash",
    "row_hash",
)
INSERT = (
    f"INSERT INTO odds_snapshots ({', '.join(COLUMNS)}) VALUES ({', '.join(['%s'] * len(COLUMNS))})"
)


@pytest.fixture(autouse=True)
def _child_imports_this_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYTHONPATH", str(REPO / "src"))


def _insert(cur: psycopg.Cursor[Any], rows: Sequence[dict[str, Any]]) -> None:
    cur.executemany(INSERT, [tuple(row[name] for name in COLUMNS) for row in rows])


def _seed(url: str, rows: tuple[dict[str, Any], ...]) -> None:
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO leagues VALUES "
            "('e2e.1', 'k1', 'Deneme Ligi', 'Testland', 'tr', 'TR', true), "
            "('e2e.9', 'k9', 'Uyuyan Lig', 'Testland', 'tr', 'TR', false)"
        )
        cur.executemany(
            "INSERT INTO matches (id, league_id, commence_time, home_team, away_team) "
            "VALUES (%s, %s, %s, %s, %s)",
            MATCHES,
        )
        start = 0
        for position, burned in sorted(BURNED.items()):
            _insert(cur, rows[start:position])
            with conn.transaction():  # yarıda kalan toplu yazım: geri alınır, kimlikler yanar
                _insert(cur, rows[position : position + burned])
                raise psycopg.Rollback()
            start = position
        _insert(cur, rows[start:])
        cur.execute("SELECT id FROM odds_snapshots ORDER BY id")
        assert tuple(found for (found,) in cur.fetchall()) == IDS, "kimlik boşlukları tutmadı"
    assert IDS[-1] != len(rows), "boşluksuz defter last_id = satır sayısı gerilemesini gizler"


def _export(url: str, tmp_path: Path) -> Path:
    anchors = anchored_repo(
        tmp_path / "repo",
        rows=ANCHOR_ROWS,
        last_id=IDS[ANCHOR_ROWS - 1],
        head=str(ROWS[ANCHOR_ROWS - 1]["row_hash"]),
        day="2026-09-21",
    )
    out = tmp_path / "out"
    conn = psycopg.connect(url, autocommit=True, options="-c timezone=UTC")
    try:
        conn.execute("SET ROLE site_reader")  # canlıda LOGIN'li site_reader'ın kendisi
        conn.autocommit = False
        run_export(
            conn,
            out,
            generated_at=datetime(2026, 9, 24, 12, 0, tzinfo=UTC),
            git_sha="1" * 40,
            method=devig_method(REPO / DEVIG_CONFIG_PATH),
            schema=SCHEMA,
            league_slugs={"e2e.1": "deneme-ligi"},
            anchor_dir=anchors,
        )
    finally:
        conn.close()
    return out


def _hand_to_the_site_build(out: Path) -> None:
    """§12.1: `site-db` adımının sabit dizini; `run-id` bu `verify.sh` koşusunun kimliği."""
    target = os.environ.get("SITE_E2E_DIR", "")
    if not target:
        return
    directory = Path(target)
    directory.mkdir(parents=True, exist_ok=True)
    for name in ("snapshot.json", "snapshot.sha256"):
        (directory / name).write_bytes((out / name).read_bytes())
    (directory / "run-id").write_text(os.environ.get("FE_VERIFY_RUN_ID", ""), encoding="utf-8")


@pytest.mark.leakage
def test_the_real_views_export_the_hand_computed_snapshot(
    site_db_each: str, tmp_path: Path
) -> None:
    _seed(site_db_each, ROWS)

    out = _export(site_db_each, tmp_path)

    assert sorted(path.name for path in out.iterdir()) == ["snapshot.json", "snapshot.sha256"]
    payload = (out / "snapshot.json").read_bytes()
    snapshot = json.loads(payload)
    assert (out / "snapshot.sha256").read_text(encoding="utf-8") == (
        f"{hashlib.sha256(payload).hexdigest()}  snapshot.json\n"
    )
    assert snapshot["matches"] == EXPECTED_MATCHES, "taban komşusu, holdout ya da pasif lig sızdı"
    assert snapshot["ledger"] == {
        "rows": len(ROWS),
        "last_id": IDS[-1],
        "head": ROWS[-1]["row_hash"],
        "anchor": {
            "file": "head-2026-09-21.txt",
            "rows": ANCHOR_ROWS,
            "last_id": IDS[ANCHOR_ROWS - 1],
            "head": ROWS[ANCHOR_ROWS - 1]["row_hash"],
        },
    }
    assert snapshot["leagues"] == [
        {
            "id": "e2e.1",
            "slug": "deneme-ligi",
            "name": "Deneme Ligi",
            "country": "Testland",
            "matches": 3,
            "move_distribution": None,
        }
    ]
    assert [(t["slug"], t["matches"], t["indexable"]) for t in snapshot["teams"]] == [
        ("alfa-spor", 2, False),
        ("beta-fk", 2, False),
        ("delta-sehir", 1, False),
        ("gamma-united", 1, False),
    ]
    assert snapshot["record"] == {"published": 0, "entries": [], "summary": None}
    assert (snapshot["value_badge"], snapshot["analysis"]) == (None, None)
    verified = subprocess.run(
        [
            sys.executable,
            "-m",
            "football_edge.site",
            "verify-snapshot",
            str(out / "snapshot.json"),
            "--sha256",
            str(out / "snapshot.sha256"),
        ],
        capture_output=True,
        text=True,
        cwd=REPO,
        check=False,
    )
    assert verified.returncode == 0, verified.stdout + verified.stderr
    _hand_to_the_site_build(out)


@pytest.mark.parametrize(("where", "position"), [("çıpa öncesi", 20), ("çıpa sonrası", 60)])
def test_a_tampered_price_stops_the_export_before_any_file(
    site_db_each: str, tmp_path: Path, where: str, position: int
) -> None:
    """N1: dışa aktarım GENESIS'ten hash'ler; iki konum da exit ≠ 0 ve dosya yok.

    `position` satır SIRASIDIR (kimlik değil): 20. satırın kimliği 24, 60.'nın 67.
    """
    forged = [dict(row) for row in ROWS]
    forged[position - 1]["price"] = Decimal(str(forged[position - 1]["price"])) + 1
    _seed(site_db_each, tuple(forged))

    with pytest.raises(ExportRefused, match="zincir KIRIK") as refused:
        _export(site_db_each, tmp_path)

    assert refused.value.code == EXIT_SITE_CHAIN, where
    assert not (tmp_path / "out").exists()
