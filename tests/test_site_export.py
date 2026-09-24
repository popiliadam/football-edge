"""`site export` (§5.1) sahte görünümlere karşı: tek işlem, tam zincir, iki türetim, iki dosya.

Gerçek SQL'e karşı aynı yol kapta `tests/test_site_e2e_db.py`de koşar. Burada her kırmızı dalın
ADIYLA ve DOSYA YAZMADAN durduğu sınanır.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
import pytest

from football_edge.backtest.model_config import MODEL_CONFIG_PATH, load_model_config
from football_edge.ledger import GENESIS
from football_edge.site import __main__ as site_main
from football_edge.site import export
from football_edge.site.contract import (
    DEVIG_CONFIG_PATH,
    EXIT_SITE_CHAIN,
    EXIT_SITE_CONFIG,
    EXIT_SITE_CUT,
    EXIT_SITE_INVALID,
    EXIT_SITE_NONDETERMINISTIC,
)
from football_edge.site.export import (
    ExportRefused,
    devig_method,
    other_hash_seed,
    run_export,
)
from tests.fake_site_db import FakeSiteDb
from tests.site_builders import (
    DUMP_CORRUPTIONS,
    EVEN,
    SYMMETRIC,
    Round,
    anchored_repo,
    at,
    ledger,
    payloads,
)

REPO = Path(__file__).resolve().parent.parent
SCHEMA: dict[str, Any] = json.loads(
    (REPO / "web/contract/snapshot.schema.json").read_text(encoding="utf-8")
)
NOW = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)
M1, M2 = "01" + "ab" * 15, "02" + "ab" * 15
ROUNDS = [
    Round(M1, "2026-09-20T10:00:00Z", "Alfa Spor", "Beta FK", [EVEN] * 3),
    Round(M2, "2026-09-20T11:00:00Z", "Gamma United", "Alfa Spor", [EVEN] * 3),
    Round(M1, "2026-09-22T13:00:00Z", "Alfa Spor", "Beta FK", SYMMETRIC, is_closing=True),
]
ROWS = ledger(payloads(ROUNDS))
SLUGS = {"tst.1": "deneme-ligi"}


@pytest.fixture(autouse=True)
def _child_imports_this_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    """İkinci türetim `python -m football_edge.site` alt sürecidir: kurulu paket değil bu ağaç."""
    monkeypatch.setenv("PYTHONPATH", str(REPO / "src"))


def _db(**changes: Any) -> FakeSiteDb:
    db = FakeSiteDb(
        leagues=[("tst.1", "Deneme Ligi", "Testland", True)],
        matches=[
            (M1, "tst.1", at("2026-09-22T14:00:00Z"), "Alfa Spor", "Beta FK"),
            (M2, "tst.1", at("2026-09-23T15:00:00Z"), "Gamma United", "Alfa Spor"),
        ],
        ledger=ROWS,
    )
    return replace(db, **changes)


def _anchors(tmp_path: Path, index: int = 9) -> Path:
    """Çıpa kesimin ortasında (id=10): hem çıpa öncesi hem sonrası satır var."""
    row = ROWS[index]
    return anchored_repo(
        tmp_path / "repo", rows=row["id"], last_id=row["id"], head=row["row_hash"], day="2026-09-21"
    )


def _export(db: FakeSiteDb, tmp_path: Path, **overrides: Any) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    out = tmp_path / "out"
    options: dict[str, Any] = {
        "generated_at": NOW,
        "git_sha": "1" * 40,
        "method": "power",
        "schema": SCHEMA,
        "league_slugs": overrides.pop("league_slugs", SLUGS),
        "anchor_dir": overrides.pop("anchor_dir", None) or _anchors(tmp_path),
        "derive_elsewhere": overrides.pop("derive_elsewhere", None),
    }
    run_export(db, out, **{**options, **overrides})  # type: ignore[arg-type]
    return out


def _refused(db: FakeSiteDb, tmp_path: Path, code: int, needle: str, **overrides: Any) -> None:
    with pytest.raises(ExportRefused, match=needle) as refused:
        _export(db, tmp_path, **overrides)
    assert refused.value.code == code
    out = tmp_path / "out"
    assert not out.exists() or list(out.iterdir()) == [], "kırmızı dışa aktarım dosya yazdı"


def test_a_clean_export_writes_exactly_the_two_files(tmp_path: Path) -> None:
    out = _export(_db(), tmp_path)

    assert sorted(path.name for path in out.iterdir()) == ["snapshot.json", "snapshot.sha256"]
    snapshot = json.loads((out / "snapshot.json").read_text(encoding="utf-8"))
    assert snapshot["ledger"]["rows"] == len(ROWS) and snapshot["ledger"]["last_id"] == len(ROWS)
    assert snapshot["ledger"]["head"] == ROWS[-1]["row_hash"]
    assert snapshot["ledger"]["anchor"]["file"] == "head-2026-09-21.txt"
    assert [match["id"] for match in snapshot["matches"]] == [M1, M2]


def test_the_export_runs_in_one_repeatable_read_read_only_transaction(tmp_path: Path) -> None:
    db = _db()
    _export(db, tmp_path)

    assert db.isolation_level == psycopg.IsolationLevel.REPEATABLE_READ and db.read_only is True


def test_a_transaction_that_is_not_repeatable_read_is_red(tmp_path: Path) -> None:
    """Oturum ayarı ezilmişse (ör. pooler) kesim tutarlılığı vaadi yoktur: işlem kendini ölçer."""
    _refused(_db(isolation=("read committed", "on")), tmp_path, EXIT_SITE_CUT, "REPEATABLE READ")


def test_the_whole_ledger_is_rehashed_through_the_audit_view(tmp_path: Path) -> None:
    db = _db()
    _export(db, tmp_path)
    reads = [q for q in db.queries if q.startswith("SELECT match_id")]

    assert any(q.endswith("FROM site_audit.ledger_rows ORDER BY id") for q in reads), reads
    assert not any("odds_snapshots" in q for q in db.queries), "site tabloya dokunmamalı"


def test_a_non_empty_out_dir_is_refused(tmp_path: Path) -> None:
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "eski.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ExportRefused, match="boş değil") as refused:
        _export(_db(), tmp_path)
    assert refused.value.code == EXIT_SITE_CONFIG


@pytest.mark.parametrize("where", ["before", "after"])
def test_a_tampered_price_before_or_after_the_anchor_is_red(tmp_path: Path, where: str) -> None:
    """N1: çıpa öncesi (id 4) ve sonrası (id 20) — saklanan hash'ler eski kalır."""
    index = 3 if where == "before" else 19
    forged = [dict(row) for row in ROWS]
    forged[index]["price"] = forged[index]["price"] + 1

    _refused(_db(ledger=tuple(forged)), tmp_path, EXIT_SITE_CHAIN, "zincir KIRIK")


def test_an_anchor_that_the_ledger_no_longer_produces_is_red(tmp_path: Path) -> None:
    anchors = anchored_repo(tmp_path / "repo", rows=10, last_id=10, head="f" * 64, day="2026-09-21")

    _refused(_db(), tmp_path, EXIT_SITE_CHAIN, "ÇIPA UYUŞMAZLIĞI", anchor_dir=anchors)


def test_no_anchor_is_red_not_skipped(tmp_path: Path) -> None:
    empty = tmp_path / "ledger"
    empty.mkdir()

    _refused(_db(), tmp_path, EXIT_SITE_CHAIN, "çıpasız yayın yok", anchor_dir=empty)


def test_an_unreadable_git_history_is_red_not_skipped(tmp_path: Path) -> None:
    loose = tmp_path / "loose" / "ledger"
    loose.mkdir(parents=True)
    row = ROWS[9]
    (loose / "head-2026-09-21.txt").write_text(
        f"x\nrows=10\nlast_id=10\nhead={row['row_hash']}\n", encoding="utf-8"
    )

    _refused(_db(), tmp_path, EXIT_SITE_CHAIN, "ATLANDI", anchor_dir=loose)


def test_an_unreadable_newest_anchor_is_red_not_downgraded(tmp_path: Path) -> None:
    anchors = _anchors(tmp_path)
    (anchors / "head-2026-09-22.txt").write_text("bozuk\n", encoding="utf-8")

    _refused(_db(), tmp_path, EXIT_SITE_CHAIN, "indirgeme yok", anchor_dir=anchors)


def test_a_deleted_anchor_is_red(tmp_path: Path) -> None:
    anchors = _anchors(tmp_path)
    extra = anchors / "head-2026-09-20.txt"
    extra.write_text(
        (anchors / "head-2026-09-21.txt").read_text(encoding="utf-8"), encoding="utf-8"
    )
    subprocess.run(["git", "-C", str(anchors), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(anchors), "-c", "user.email=t@example.com", "-c", "user.name=t"]
        + ["commit", "-q", "-m", "ikinci çıpa"],
        check=True,
    )
    extra.unlink()

    _refused(_db(), tmp_path, EXIT_SITE_CHAIN, "ÇIPA EKSİK", anchor_dir=anchors)


def test_a_view_that_returns_no_rows_under_the_anchor_is_red(tmp_path: Path) -> None:
    """§4.2 bekçi 3: yanlış görünüm sahibi RLS'li tabloyu 0 satır okur — DB içinden görünmez."""
    _refused(_db(head_rows=0), tmp_path, EXIT_SITE_CUT, "görünüm sahipliği")


def test_an_empty_match_set_under_a_nonempty_anchor_is_red(tmp_path: Path) -> None:
    _refused(_db(matches=[]), tmp_path, EXIT_SITE_CUT, "maç kümesi boş")


@pytest.mark.leakage
def test_a_floor_drift_between_db_and_python_is_red(tmp_path: Path) -> None:
    _refused(_db(floor=at("2026-07-01T00:00:00Z")), tmp_path, EXIT_SITE_CUT, "tabanından farklı")


def test_a_different_second_derivation_is_red(tmp_path: Path) -> None:
    _refused(
        _db(),
        tmp_path,
        EXIT_SITE_NONDETERMINISTIC,
        "farklı content_sha256",
        derive_elsewhere=lambda dump: "0" * 64,
    )


def test_a_snapshot_that_fails_verify_is_not_written(tmp_path: Path) -> None:
    """H2: bir takım adı bağlantı taşıyorsa anlık görüntü yazılmaz."""
    matches = [(M1, "tst.1", at("2026-09-22T14:00:00Z"), "http://x.invalid", "Beta FK")]
    rounds = [Round(M1, "2026-09-20T10:00:00Z", "http://x.invalid", "Beta FK", [EVEN] * 3)]
    rows = ledger(payloads(rounds))
    anchors = anchored_repo(
        tmp_path / "repo", rows=3, last_id=3, head=rows[2]["row_hash"], day="2026-09-21"
    )

    _refused(
        _db(matches=matches, ledger=rows),
        tmp_path,
        EXIT_SITE_INVALID,
        "verify-snapshot",
        anchor_dir=anchors,
    )


def test_the_devig_method_is_the_model_config_method() -> None:
    """Site `backtest`i import edemez (H1f); aynı dosyadan okunan yöntem modelinkine eşit olmalı."""
    assert DEVIG_CONFIG_PATH == MODEL_CONFIG_PATH
    assert (
        devig_method(REPO / DEVIG_CONFIG_PATH) == load_model_config(REPO / MODEL_CONFIG_PATH).method
    )


def test_the_other_seed_differs_from_this_process_seed() -> None:
    assert other_hash_seed({"PYTHONHASHSEED": "1"}) == "2"
    assert other_hash_seed({"PYTHONHASHSEED": "7"}) == "1"
    assert other_hash_seed({}) == "1"


def _publication(clv: float) -> tuple[Any, ...]:
    """M1'in kapanışı simetrik (1/3): 3.12 × 1/3 − 1 = 0.04."""
    return (
        1,
        M1,
        "h2h",
        "home",
        at("2026-09-21T09:00:00Z"),
        Decimal("3.12"),
        3,
        Decimal("3"),
        clv,
        "1" * 64,
    )


def test_a_consistent_record_is_exported_with_its_summary(tmp_path: Path) -> None:
    out = _export(_db(record=[_publication(3.12 / 3 - 1)]), tmp_path)
    record = json.loads((out / "snapshot.json").read_text(encoding="utf-8"))["record"]

    assert record["published"] == 1 and record["entries"][0]["clv"] == 4.0
    assert record["summary"] == {"mean_clv": 4.0, "ci_low": 4.0, "ci_high": 4.0, "n": 1}


def test_a_record_entry_the_ledger_cannot_reproduce_is_red(tmp_path: Path) -> None:
    """§6.4/3d: CLV defterin kapanış konsensüsünden yeniden hesaplanır; uyuşmazsa yayın yok."""
    _refused(_db(record=[_publication(0.5)]), tmp_path, EXIT_SITE_CUT, "CLV defterden")


def test_an_active_league_without_a_configured_slug_is_red(tmp_path: Path) -> None:
    """I3: lig slug'ı addan türetilmez; yapılandırmada yoksa yayın yok (exit 20, lig adıyla)."""
    _refused(_db(), tmp_path, EXIT_SITE_CONFIG, "slug'ı olmayan lig: tst.1", league_slugs={})


def test_the_league_slug_comes_from_configuration_not_from_the_name(tmp_path: Path) -> None:
    out = _export(_db(), tmp_path, league_slugs={"tst.1": "kuzey-bolgesi"})
    leagues = json.loads((out / "snapshot.json").read_text(encoding="utf-8"))["leagues"]

    assert [(league["name"], league["slug"]) for league in leagues] == [
        ("Deneme Ligi", "kuzey-bolgesi")
    ]


# ── Review Focus ──────────────────────────────────────────────────────────────────────────────


def test_review_focus_a_non_utc_session_exports_the_same_content(tmp_path: Path) -> None:
    """Pooler `-c timezone=UTC`yi yok sayarsa psycopg +03:00'lı zaman döner; içerik değişmemeli."""
    istanbul = timezone(timedelta(hours=3))
    shifted = tuple({**row, "observed_at": row["observed_at"].astimezone(istanbul)} for row in ROWS)
    base = _db()
    local = _db(
        ledger=shifted,
        matches=[(m[0], m[1], m[2].astimezone(istanbul), m[3], m[4]) for m in base.matches],
    )
    utc_out = _export(base, tmp_path / "utc")
    local_out = _export(local, tmp_path / "ist")

    def content(out: Path) -> str:
        return str(
            json.loads((out / "snapshot.json").read_text(encoding="utf-8"))["content_sha256"]
        )

    assert content(local_out) == content(utc_out)


def test_review_focus_an_anchor_beyond_the_cut_is_red(tmp_path: Path) -> None:
    """Eski veritabanına yeni checkout: çıpa kesimde olmayan satırı gösterir → adıyla kırmızı."""
    anchors = anchored_repo(
        tmp_path / "repo", rows=999, last_id=999, head="e" * 64, day="2026-09-21"
    )

    _refused(_db(), tmp_path, EXIT_SITE_CHAIN, "id=999", anchor_dir=anchors)


# ── Bozuk döküm: adlandırılmış çıkış, metin değil sınıf (Task 5 taşıması) ─────────────────────


def _corrupted(monkeypatch: pytest.MonkeyPatch, old: str, new: str) -> None:
    real = export.dump_text

    def corrupt(**parts: Any) -> str:
        text = real(**parts)
        assert old in text, f"bozma çapası yok: {old!r}"
        return text.replace(old, new, 1)

    monkeypatch.setattr(export, "dump_text", corrupt)


@pytest.mark.parametrize(
    ("old", "new", "kind"), [case for case in DUMP_CORRUPTIONS if case[2] != "DeriveError"]
)
def test_an_undecodable_dump_is_a_named_exit_that_prints_the_class_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, old: str, new: str, kind: str
) -> None:
    """Eksik anahtar, sürüm, bool olmayan, fiyat olmayan, biçim: exit 22, yalnız sınıf adı."""
    _corrupted(monkeypatch, old, new)

    with pytest.raises(ExportRefused) as refused:
        _export(_db(), tmp_path)

    assert refused.value.code == EXIT_SITE_CUT
    assert str(refused.value) == f"girdi dökümü çözülemedi ({kind})"
    assert not (tmp_path / "out").exists()


def test_a_dump_time_that_is_not_canonical_utc_is_a_named_derive_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Naive zaman `load_inputs`te `DeriveError`dır: çözme de `DeriveError` eşlemesinin içinde."""
    old, new, _ = next(case for case in DUMP_CORRUPTIONS if case[2] == "DeriveError")
    _corrupted(monkeypatch, old, new)

    _refused(_db(), tmp_path, EXIT_SITE_CUT, "kanonik UTC metni değil")


# ── Düzeltme turu 1: tek işlem, her çıpa, atomik yazma, hash dosyası, taban, baş görünümü ────


def test_the_chain_and_the_dump_are_read_in_one_transaction(tmp_path: Path) -> None:
    """B12: taklit işlem dışındaki sorguyu reddeder; zincir de döküm de TEK işlemde okunur."""
    db = _db()
    _export(db, tmp_path)

    assert db.transactions == 1
    assert any(q.startswith("SELECT match_id") for q in db.queries)
    assert any("FROM site_input.h2h_quotes" in q for q in db.queries)


def _commit_anchor(anchors: Path, name: str, content: str | bytes) -> None:
    """Çıpa deposuna ikinci (eski tarihli) bir çıpa commit'ler."""
    target = anchors / name
    if isinstance(content, bytes):
        target.write_bytes(content)
    else:
        target.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(anchors), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(anchors), "-c", "user.email=t@example.com", "-c", "user.name=t"]
        + ["commit", "-q", "-m", "eski çıpa"],
        check=True,
    )


def _anchor_text(*, rows: int, last_id: int, head: str) -> str:
    return f"2026-09-20T12:00:00+00:00\nrows={rows}\nlast_id={last_id}\nhead={head}\n"


OLDER = "head-2026-09-20.txt"


def test_every_anchor_is_asked_not_only_the_newest(tmp_path: Path) -> None:
    """§5.1/1: eski çıpanın hash'i defterle uyuşmuyorsa en yenisi tutsa da kırmızı."""
    anchors = _anchors(tmp_path)
    _commit_anchor(anchors, OLDER, _anchor_text(rows=5, last_id=5, head="f" * 64))

    _refused(_db(), tmp_path, EXIT_SITE_CHAIN, f"ÇIPA UYUŞMAZLIĞI.*{OLDER}", anchor_dir=anchors)


@pytest.mark.parametrize(
    ("content", "needle"),
    [
        ("bozuk\n", f"okunamayan çıpa: {OLDER}"),
        (b"\xff\xfe bozuk", r"çıpa dosyası okunamadı \(UnicodeDecodeError\)"),
    ],
)
def test_an_unreadable_older_anchor_is_red_not_dropped(
    tmp_path: Path, content: str | bytes, needle: str
) -> None:
    """Okunamayan ESKİ çıpa sessizce düşmez: sorulmayan çıpa da bir indirgemedir."""
    anchors = _anchors(tmp_path)
    _commit_anchor(anchors, OLDER, content)

    _refused(_db(), tmp_path, EXIT_SITE_CHAIN, needle, anchor_dir=anchors)


@pytest.mark.parametrize(
    ("rows", "head"),
    [(10, "e" * 64), (10, GENESIS), (0, "e" * 64)],
    ids=["both", "rows-only", "head-only"],
)
def test_an_inconsistent_empty_ledger_anchor_is_red(tmp_path: Path, rows: int, head: str) -> None:
    """`last_id=0` çıpası `_first_anchor_break`te atlanır; satır sayan YA DA GENESIS dışı baş
    taşıyorsa boş defterin çıpası değildir — iki koşul ayrı ayrı yeter (T6 N2)."""
    anchors = _anchors(tmp_path)
    _commit_anchor(anchors, OLDER, _anchor_text(rows=rows, last_id=0, head=head))

    _refused(
        _db(), tmp_path, EXIT_SITE_CHAIN, f"boş defter çıpası tutarsız: {OLDER}", anchor_dir=anchors
    )


def test_a_newest_empty_ledger_anchor_under_a_nonempty_ledger_is_red(tmp_path: Path) -> None:
    anchors = anchored_repo(tmp_path / "repo", rows=0, last_id=0, head=GENESIS, day="2026-09-21")

    _refused(_db(), tmp_path, EXIT_SITE_CHAIN, "en yeni çıpa boş defteri", anchor_dir=anchors)


def test_a_consistent_empty_ledger_anchor_from_the_past_is_accepted(tmp_path: Path) -> None:
    """Defter boşken yazılmış çıpa gerçek bir geçmiş hâldir; çıpalar silinmez, kalıcı red olmaz."""
    anchors = _anchors(tmp_path)
    _commit_anchor(anchors, OLDER, _anchor_text(rows=0, last_id=0, head=GENESIS))

    out = _export(_db(), tmp_path, anchor_dir=anchors)
    assert sorted(path.name for path in out.iterdir()) == ["snapshot.json", "snapshot.sha256"]


@pytest.mark.parametrize("override", [{"head_rows": 20}, {"head_last_id": 99}])
def test_a_ledger_head_that_disagrees_with_the_verified_chain_is_red(
    tmp_path: Path, override: dict[str, int]
) -> None:
    """`site.ledger_head` ve `site_audit.ledger_rows` aynı tabloya aynı işlemde bakar."""
    _refused(
        _db(**override), tmp_path, EXIT_SITE_CUT, "site.ledger_head doğrulanan zincirle uyuşmuyor"
    )


def test_a_failed_write_leaves_no_file_and_is_named(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """I3: ikinci dosya yazılamazsa `--out`ta yarım anlık görüntü kalmaz; çıkış adlı, sınıf adı."""
    anchors = _anchors(tmp_path)
    real = Path.write_text

    def full_disk(self: Path, *args: Any, **kwargs: Any) -> int:
        if self.name == "snapshot.sha256":
            raise OSError(28, "No space left on device", str(self))
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", full_disk)

    with pytest.raises(ExportRefused) as refused:
        _export(_db(), tmp_path, anchor_dir=anchors)

    assert refused.value.code == EXIT_SITE_CONFIG
    assert str(refused.value) == "çıktı yazılamadı (OSError)"
    assert not (tmp_path / "out").exists()
    assert [p for p in tmp_path.rglob("snapshot.*")] == [], "hazırlama dosyası kaldı"


def test_the_files_are_staged_outside_out_until_both_are_written(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Yazım anında `--out` yoktur: iki dosya hazırlama dizinine yazılır, dizin sonra taşınır.

    Sınır: yazımı `--out`a yapıp hatada temizleyen bir uygulama yukarıdaki hata testini geçer;
    süreç öldürülürse (temizlik koşmaz) yarım yayın kalır. Bu test onu ayırır.
    """
    anchors = _anchors(tmp_path)
    out = tmp_path / "out"
    seen: list[tuple[str, bool]] = []
    real_bytes, real_text = Path.write_bytes, Path.write_text

    def spy_bytes(self: Path, data: Any) -> int:
        seen.append((self.name, out.exists()))
        return real_bytes(self, data)

    def spy_text(self: Path, *args: Any, **kwargs: Any) -> int:
        seen.append((self.name, out.exists()))
        return real_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_bytes", spy_bytes)
    monkeypatch.setattr(Path, "write_text", spy_text)

    _export(_db(), tmp_path, anchor_dir=anchors)

    assert seen == [("snapshot.json", False), ("snapshot.sha256", False)]
    assert sorted(path.name for path in out.iterdir()) == ["snapshot.json", "snapshot.sha256"]


def test_an_out_path_that_is_a_file_is_refused_by_name(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "out").write_text("eski", encoding="utf-8")

    with pytest.raises(ExportRefused, match="boş değil") as refused:
        _export(_db(), tmp_path)

    assert refused.value.code == EXIT_SITE_CONFIG
    assert (tmp_path / "out").read_text(encoding="utf-8") == "eski"


def test_an_existing_empty_out_dir_receives_the_two_files(tmp_path: Path) -> None:
    """Hazırlama dizini boş `--out`un yerine geçer (POSIX rename boş dizinin üstüne izinli)."""
    (tmp_path / "out").mkdir(parents=True)

    out = _export(_db(), tmp_path)

    assert sorted(path.name for path in out.iterdir()) == ["snapshot.json", "snapshot.sha256"]


def test_the_hash_file_is_the_sha256sum_line_of_the_snapshot_bytes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`<dosya baytlarının sha256'sı>  snapshot.json` + satır sonu: `sha256sum -c` biçimi.

    Dosya baytlarının hash'i — içerik hash'i (`content_sha256`) DEĞİL.
    """
    out = _export(_db(), tmp_path)
    payload = (out / "snapshot.json").read_bytes()

    expected = f"{hashlib.sha256(payload).hexdigest()}  snapshot.json\n"
    assert (out / "snapshot.sha256").read_bytes() == expected.encode("utf-8")
    monkeypatch.chdir(REPO)
    monkeypatch.setattr(site_main, "configure_logging", lambda: None)
    verified = site_main.main(
        ["verify-snapshot", str(out / "snapshot.json"), "--sha256", str(out / "snapshot.sha256")]
    )
    assert verified == 0


class _FloorlessViewDb(FakeSiteDb):
    """Tabanı süzmeyen `site.matches` (bozuk görünüm): dışa aktarıcının kendi taban bekçisi."""

    def site_matches(self) -> list[tuple[str, str, datetime, str, str]]:
        active = {league[0] for league in self.leagues if league[3]}
        return sorted((row for row in self.matches if row[1] in active), key=lambda row: row[0])


@pytest.mark.leakage
def test_a_view_that_returns_a_match_below_the_floor_is_red(tmp_path: Path) -> None:
    """H1(d): görünüm tabandan eski bir maç döndürürse dışa aktarım adıyla durur."""
    base = _db()
    old = ("03" + "ab" * 15, "tst.1", at("2026-06-20T18:00:00Z"), "Eski Spor", "Tarih FK")
    db = _FloorlessViewDb(leagues=base.leagues, matches=[*base.matches, old], ledger=ROWS)

    _refused(db, tmp_path, EXIT_SITE_CUT, "görünüm tabandan eski")
