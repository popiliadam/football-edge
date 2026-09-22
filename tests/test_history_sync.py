"""`history/sync.py`: sahte veritabanı, `httpx.MockTransport`, sentetik CSV — ağ yok."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest
from protego import Protego

from football_edge.collector import ContractViolation
from football_edge.history.catalog import Catalog, declared_paths, load_catalog
from football_edge.history.holdout import DEV, HOLDOUT, POST, HoldoutKey, HoldoutLocked, period_of
from football_edge.history.lock import LockViolation, build_lock
from football_edge.history.store import save_file
from football_edge.history.sync import SyncReport, _load_all, load_matches, mutable_paths, sync
from football_edge.history.types import HistMatch
from tests.fake_hist_db import FakeHistDb, at
from tests.fake_sources import fake_source
from tests.history_csv import (
    BRA,
    E0,
    EXTRA_NEW,
    MAIN_2526,
    MAIN_2627,
    csv_bytes,
    extra_row,
    main_row,
    widen,
)

CATALOG = Catalog(current_season="2627", leagues=(E0, BRA))
OLD, CURRENT, EXTRA_FILE = "/mmz4281/2526/E0.csv", "/mmz4281/2627/E0.csv", "/new/BRA.csv"
FILES: Mapping[str, bytes] = {
    OLD: csv_bytes(MAIN_2526, [main_row(n) for n in range(3)]),
    CURRENT: csv_bytes(MAIN_2627, [main_row(n, {"Date": "22/08/2026"}) for n in range(2)]),
    EXTRA_FILE: csv_bytes(EXTRA_NEW, [extra_row(n) for n in range(2)]),
}
OPEN_ROBOTS = "User-agent: *\nDisallow:\n"
# Dönem karışık önbellek: E0'ın 2025/26 dosyası holdout, 2026/27 dosyası sonrası; ek lig dosyası
# bütün yılları taşır — geliştirme, holdout ve sonrası birer satır.
PERIODS_FILES: Mapping[str, bytes] = {
    **FILES,
    EXTRA_FILE: csv_bytes(
        EXTRA_NEW,
        [
            extra_row(0, {"Season": "2024", "Date": "20/10/2024"}),
            extra_row(1, {"Season": "2025", "Date": "16/08/2025"}),
            extra_row(2, {"Season": "2026", "Date": "20/08/2026"}),
        ],
    ),
}


class Site:
    """football-data taklidi: yol → yanıt; gelen her isteğin yolunu kaydeder."""

    def __init__(self, files: Mapping[str, bytes], status: Mapping[str, int] | None = None) -> None:
        self.files = dict(files)
        self.status = dict(status or {})
        self.requested: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requested = [*self.requested, request.url.path]
        code = self.status.get(request.url.path, 200)
        body = self.files.get(request.url.path, b"") if code == 200 else b""
        return httpx.Response(code, content=body, headers={"last-modified": "Mon, 21 Sep 2026"})


def ticking() -> Callable[[], datetime]:
    minutes = iter(range(60))
    return lambda: at(next(minutes))


def run(
    db: FakeHistDb,
    site: Site,
    paths: tuple[str, ...] = (OLD, CURRENT, EXTRA_FILE),
    *,
    robots: str = OPEN_ROBOTS,
    declared: tuple[str, ...] = (OLD, CURRENT, EXTRA_FILE),
) -> SyncReport:
    source = fake_source(
        id="football-data", base_url="https://football-data.co.uk", declared_paths=declared
    )
    with httpx.Client(transport=httpx.MockTransport(site)) as client:
        return sync(
            db,
            client,
            source=source,
            parser=Protego.parse(robots),
            catalog=CATALOG,
            paths=paths,
            now=ticking(),
        )


def test_mutable_paths_are_the_current_main_seasons_and_every_extra_file() -> None:
    assert mutable_paths(CATALOG) == (CURRENT, EXTRA_FILE)

    real = load_catalog(Path(__file__).resolve().parent.parent / "config/history_leagues.yaml")
    paths = mutable_paths(real)
    assert len(paths) == 22 + 16
    assert set(paths) <= set(declared_paths(real))
    assert all(path.startswith(("/mmz4281/2627/", "/new/")) for path in paths)


def test_sync_caches_every_file_and_logs_every_fetch() -> None:
    db, site = FakeHistDb(), Site(FILES)

    report = run(db, site)

    assert report == SyncReport(requested=3, changed=3, unchanged=0, failed=(), rejected_rows=0)
    assert site.requested == [OLD, CURRENT, EXTRA_FILE]
    assert set(db.files) == {OLD, CURRENT, EXTRA_FILE}
    assert [(row["path"], row["http_status"], row["rows_parsed"]) for row in db.fetches] == [
        (OLD, 200, 3),
        (CURRENT, 200, 2),
        (EXTRA_FILE, 200, 2),
    ]
    assert [row["fetched_at"] for row in db.fetches] == [at(0), at(1), at(2)]
    assert all(row["sha256"] for row in db.fetches)
    assert db.files[OLD]["http_last_modified"] == "Mon, 21 Sep 2026", "Last-Modified kayboldu"
    assert db.commits == 3, "her dosya kendi işleminde commit'lenmeli"


def test_an_unchanged_second_run_rewrites_nothing_but_still_logs_the_fetches() -> None:
    db, site = FakeHistDb(), Site(FILES)
    run(db, site)

    report = run(db, site)

    assert (report.changed, report.unchanged, report.failed) == (0, 3, ())
    assert len(db.fetches) == 6


def test_a_failing_file_is_named_and_the_others_still_sync() -> None:
    db, site = FakeHistDb(), Site(FILES, status={OLD: 404})

    report = run(db, site)

    ((path, reason),) = report.failed
    assert path == OLD and "404" in reason and "\n" not in reason
    assert (report.changed, report.unchanged) == (2, 0)
    assert set(db.files) == {CURRENT, EXTRA_FILE}
    assert (db.fetches[0]["sha256"], db.fetches[0]["http_status"]) == (None, 404)


def test_a_file_that_breaks_the_contract_never_replaces_the_cached_version() -> None:
    db = FakeHistDb()
    run(db, Site(FILES))
    good = db.files[EXTRA_FILE]["sha256"]
    broken = csv_bytes(tuple(n for n in EXTRA_NEW if n != "Res"), [extra_row(0)])

    report = run(db, Site({**FILES, EXTRA_FILE: broken}))

    ((path, reason),) = report.failed
    assert path == EXTRA_FILE and "ContractViolation" in reason and "zorunlu sütun" in reason
    assert db.files[EXTRA_FILE]["sha256"] == good
    assert (db.fetches[-1]["sha256"], db.fetches[-1]["http_status"]) == (None, None)


def test_rejected_rows_under_the_limit_are_counted_not_hidden() -> None:
    rows = [main_row(n) for n in range(199)] + [main_row(199, {"FTR": "A"})]
    db = FakeHistDb()

    report = run(db, Site({**FILES, OLD: csv_bytes(MAIN_2526, rows)}), (OLD,))

    assert (report.changed, report.rejected_rows) == (1, 1)
    assert (db.fetches[0]["rows_parsed"], db.fetches[0]["rows_rejected"]) == (199, 1)
    assert db.files[OLD]["row_count"] == 199


def test_trimmed_rows_are_logged_per_file_as_a_count_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """R111: kırpma sessiz geçmez — dosya başına tek INFO satırı, yalnız sayı (hücre değeri yok)."""
    rows = [main_row(n, {"HomeTeam": f"Gizli {n}"}) for n in range(3)]
    widened = widen(widen(csv_bytes(MAIN_2526, rows), 1, ",,,"), 3, ", ,")
    db = FakeHistDb()

    with caplog.at_level("INFO", logger="football_edge.history.sync"):
        report = run(db, Site({**FILES, OLD: widened}))

    assert (report.failed, report.rejected_rows) == ((), 0)
    assert db.fetches[0]["rows_parsed"] == 3
    trimmed = [record for record in caplog.records if "kırpıldı" in record.getMessage()]
    assert [(record.levelname, record.args) for record in trimmed] == [("INFO", (OLD, 2))]
    assert not any("Gizli" in record.getMessage() for record in caplog.records)


def test_a_file_that_fails_the_contract_still_logs_its_trim_count(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Kırpma satırı sözleşme denetiminden ÖNCE yazılır: düşen dosyanın kırpma sayısı da görünür."""
    rows = [main_row(0), *(main_row(n, {"FTR": "A", "HomeTeam": f"Gizli {n}"}) for n in (1, 2))]
    widened = widen(csv_bytes(MAIN_2526, rows), 1, ",,,")
    db = FakeHistDb()

    with caplog.at_level("INFO", logger="football_edge.history.sync"):
        report = run(db, Site({**FILES, OLD: widened}), (OLD,))

    ((path, reason),) = report.failed
    assert path == OLD and "ContractViolation" in reason and "reddedilen satır" in reason
    trimmed = [record for record in caplog.records if "kırpıldı" in record.getMessage()]
    assert [(record.levelname, record.args) for record in trimmed] == [("INFO", (OLD, 1))]
    assert not any("Gizli" in record.getMessage() for record in trimmed)


def test_a_file_without_trimmed_rows_logs_no_trim_line(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("INFO", logger="football_edge.history.sync"):
        run(FakeHistDb(), Site(FILES))

    assert not [record for record in caplog.records if "kırpıldı" in record.getMessage()]


def test_an_undeclared_path_is_never_requested() -> None:
    db, site = FakeHistDb(), Site(FILES)

    report = run(db, site, declared=(OLD, CURRENT))

    assert [path for path, _ in report.failed] == [EXTRA_FILE]
    assert "SourceBlocked" in report.failed[0][1]
    assert EXTRA_FILE not in site.requested


def test_a_path_robots_forbids_is_never_requested() -> None:
    db, site = FakeHistDb(), Site(FILES)

    report = run(db, site, robots="User-agent: *\nDisallow: /new/\n")

    assert [path for path, _ in report.failed] == [EXTRA_FILE]
    assert EXTRA_FILE not in site.requested


def test_a_failed_commit_is_a_failure_not_a_change() -> None:
    """G1: commit düşerse satırlar geri alınır; sayaç onları yazılmış saymamalı."""
    first = iter([True])
    db = FakeHistDb(commit_fails=lambda _: next(first, False))

    report = run(db, Site(FILES))

    assert [path for path, _ in report.failed] == [OLD]
    assert "CommitFailed" in report.failed[0][1]
    assert report.changed == 2 and OLD not in db.files
    assert report.requested == report.changed + report.unchanged + len(report.failed)


# ── _load_all / load_matches ────────────────────────────────────────────────


def test_load_all_returns_every_cached_season_in_date_kickoff_home_order() -> None:
    rows_old = [
        main_row(0, {"Date": "23/08/2025"}),
        main_row(3, {"Date": "16/08/2025", "Time": "17:30"}),
        main_row(2, {"Date": "16/08/2025", "Time": "12:30"}),
        main_row(1, {"Date": "16/08/2025", "Time": "12:30"}),
        main_row(9, {"Date": "16/08/2025", "Time": ""}),
    ]
    db = FakeHistDb()
    run(db, Site({**FILES, OLD: csv_bytes(MAIN_2526, rows_old)}))

    loaded = _load_all(db, CATALOG)

    assert set(loaded) == {"E0", "BRA"}
    e0 = loaded["E0"]
    assert [(match.date, match.home) for match in e0] == [
        (date(2025, 8, 16), "Ev 9"),
        (date(2025, 8, 16), "Ev 1"),
        (date(2025, 8, 16), "Ev 2"),
        (date(2025, 8, 16), "Ev 3"),
        (date(2025, 8, 23), "Ev 0"),
        (date(2026, 8, 22), "Ev 0"),
        (date(2026, 8, 22), "Ev 1"),
    ]
    assert e0[0].kickoff is None and e0[1].kickoff == datetime(2025, 8, 16, 11, 30, tzinfo=UTC)
    assert {match.season for match in e0} == {"2526", "2627"}
    assert len(loaded["BRA"]) == 2


def test_load_matches_refuses_an_incomplete_cache() -> None:
    db = FakeHistDb()
    run(db, Site(FILES), (OLD, EXTRA_FILE))

    with pytest.raises(ContractViolation, match=f"1 dosya yok.*{CURRENT}"):
        load_matches(db, CATALOG)


def _periods(loaded: Mapping[str, tuple[HistMatch, ...]]) -> dict[str, list[str]]:
    return {code: sorted({period_of(m.date) for m in matches}) for code, matches in loaded.items()}


def _cached_periods() -> FakeHistDb:
    db = FakeHistDb()
    run(db, Site(PERIODS_FILES))
    return db


@pytest.mark.leakage
def test_load_matches_without_a_key_never_hands_out_a_holdout_row() -> None:
    """R96: holdout satırları `history/`den anahtarsız çıkmaz — `_load_all` onları taşır."""
    db = _cached_periods()

    everything, loaded = _load_all(db, CATALOG), load_matches(db, CATALOG)

    assert _periods(everything) == {"E0": [HOLDOUT, POST], "BRA": [DEV, HOLDOUT, POST]}
    assert _periods(loaded) == {"E0": [POST], "BRA": [DEV, POST]}
    assert [match.date for match in loaded["BRA"]] == [date(2024, 10, 20), date(2026, 8, 20)]


@pytest.mark.leakage
def test_a_hand_built_key_does_not_open_the_holdout() -> None:
    forged = HoldoutKey(opened_at=at(0), purpose="deneme", git_sha="0" * 40)

    with pytest.raises(HoldoutLocked):
        load_matches(_cached_periods(), CATALOG, key=forged)


@pytest.mark.leakage
def test_the_lock_is_checked_over_every_period_before_the_holdout_is_filtered_out() -> None:
    """Süzgeçten SONRA doğrulansaydı kilitteki holdout özeti eksik satırlarla tutmazdı."""
    db = _cached_periods()
    lock = build_lock(_load_all(db, CATALOG), locked_at=date(2026, 9, 28))

    loaded = load_matches(db, CATALOG, lock=lock)

    assert _periods(loaded) == {"E0": [POST], "BRA": [DEV, POST]}


@pytest.mark.leakage
def test_a_changed_holdout_row_breaks_the_lock_although_it_is_never_returned() -> None:
    db = _cached_periods()
    lock = build_lock(_load_all(db, CATALOG), locked_at=date(2026, 9, 28))
    rescored = [main_row(0, {"FTHG": "3"}), main_row(1), main_row(2)]
    run(db, Site({**PERIODS_FILES, OLD: csv_bytes(MAIN_2526, rescored)}))

    with pytest.raises(LockViolation):
        load_matches(db, CATALOG, lock=lock)


def test_load_matches_rechecks_the_contract_of_every_cached_file() -> None:
    """Önbelleğe bugünkü sözleşmeyi geçmeyen bir dosya girdiyse (eski kod, elle yazım) yükleme
    onu sessizce eksik satırla kullanmaz."""
    db = FakeHistDb()
    run(db, Site(FILES))
    broken = csv_bytes(tuple(n for n in MAIN_2627 if n != "FTAG"), [main_row(0)])
    save_file(db, path=CURRENT, content=broken, fetched_at=at(30), last_modified=None, row_count=0)

    with pytest.raises(ContractViolation, match="zorunlu sütun"):
        load_matches(db, CATALOG)
