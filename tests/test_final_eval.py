"""Faz 3'ün tek holdout açılışı (Faz 3 tasarımı §8; R130, R135): ön kayıt, sayım, sıra, satırlar.

Veritabanı yok: `open_holdout` ve `load_matches` `final_eval` modülünde yamalanır ve ÇAĞRI SIRASI
kaydedilir; değerlendirme SENTETİK sezonlarda gerçekten koşar.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from football_edge.backtest import final_eval
from football_edge.backtest.final_eval import (
    AlreadyOpened,
    HoldoutCountMismatch,
    OpenedButFailed,
    check_holdout_count,
    previous_openings,
    purpose_for,
    render_final,
    run_final,
    run_rehearsal,
)
from football_edge.backtest.model_config import MODEL_CONFIG_PATH, ModelConfig, file_sha256
from football_edge.backtest.preregistration import (
    PHASES,
    CanonicalPaths,
    Git,
    PreflightError,
    Preregistration,
    load_preregistration,
    preflight,
    probe_out_dir,
)
from football_edge.backtest.walkforward import MISSING_REASONS
from football_edge.backtest.wf_run import format_counts
from football_edge.history.catalog import MAIN, Catalog, HistoryLeague
from football_edge.history.holdout import HOLDOUT, POST, HoldoutKey, period_of
from football_edge.history.lock import LockViolation, build_lock
from football_edge.market.devig import POWER
from football_edge.model.dixon_coles import DCConfig
from football_edge.model.elo_model import EloModelConfig
from tests.model_builders import TEAMS, main_history
from tests.workflow_helpers import MIGRATIONS

SHA = "a" * 40
REPO = Path(__file__).resolve().parent.parent
COMPARISONS = PHASES["faz3"]
NOW = datetime(2026, 10, 20, 12, tzinfo=UTC)
CATALOG = Catalog("2627", (HistoryLeague("E0", "t.1", "Test", "Ülke", 1, MAIN, "1112", ""),))
EVERYTHING = {"E0": main_history(2011, 2026)}
LOCK = build_lock(EVERYTHING, locked_at=date(2026, 9, 22))
PREREG = Preregistration("faz3", "m", "l", "c", COMPARISONS, 0.02, (0.0, 0.05), 50)
CONFIG = ModelConfig(
    "2026-10-01", "c", "l", POWER, EloModelConfig(), DCConfig(min_matches=40), 7, 0.02, (0.0,)
)


def test_the_first_opening_carries_the_preregistration_hash() -> None:
    assert (
        purpose_for(
            (),
            phase="faz3",
            prereg_sha256="p" * 64,
            git_sha=SHA,
            report_exists=False,
            rerun_reason=None,
        )
        == "faz3:" + "p" * 64
    )


@pytest.mark.leakage
@pytest.mark.parametrize(
    ("previous", "report", "sha", "reason"),
    [
        ((("faz3:x", SHA),), False, SHA, None),  # ikinci açılış, neden yok
        ((("faz3:x", SHA),), True, SHA, "çöktü"),  # rapor üretilmiş
        ((("faz3:x", "b" * 40),), False, SHA, "çöktü"),  # kod değişmiş
        ((("faz3:x", SHA), ("faz3-rerun:y:x", SHA)), False, SHA, "yine"),  # ikinci yeniden koşu
        ((), False, SHA, "çöktü"),  # açılış yokken yeniden koşu
        ((("faz3:x", SHA),), False, SHA, "  "),  # boş neden
    ],
)
def test_a_second_opening_is_refused_unless_the_rerun_rule_holds(
    previous: tuple[tuple[str, str], ...], report: bool, sha: str, reason: str | None
) -> None:
    with pytest.raises(AlreadyOpened):
        purpose_for(
            previous,
            phase="faz3",
            prereg_sha256="p",
            git_sha=sha,
            report_exists=report,
            rerun_reason=reason,
        )


def test_one_logged_rerun_after_a_crash_without_a_report() -> None:
    found = purpose_for(
        (("faz3:p", SHA),),
        phase="faz3",
        prereg_sha256="p",
        git_sha=SHA,
        report_exists=False,
        rerun_reason="OOM",
    )

    assert found == "faz3-rerun:OOM:p"


def _git(*, clean: bool = True, committed: bool = True) -> Git:
    return Git(head=lambda: SHA, clean=lambda: clean, committed=lambda path: committed)


def _prereg_files(tmp: Path) -> dict[str, Path]:
    paths = {name: tmp / f"{name}.yaml" for name in ("model", "lock", "catalog")}
    for name, path in paths.items():
        path.write_text(f"{name}\n", encoding="utf-8")
    prereg = tmp / "prereg.yaml"
    prereg.write_text(
        "phase: faz3\n"
        f"model_config_sha256: {file_sha256(paths['model'])}\n"
        f"lock_sha256: {file_sha256(paths['lock'])}\n"
        f"catalog_sha256: {file_sha256(paths['catalog'])}\n"
        "comparisons: [C1, C2, C3, C4, C5, C6]\n"
        "tau: 0.02\nsensitivity: [0.0, 0.05]\nresamples: 2000\n",
        encoding="utf-8",
    )
    return {**paths, "prereg": prereg}


def _canonical(paths: dict[str, Path]) -> CanonicalPaths:
    return CanonicalPaths(
        prereg=paths["prereg"], model=paths["model"], lock=paths["lock"], catalog=paths["catalog"]
    )


def _preflight(
    paths: dict[str, Path], git: Git, canonical: CanonicalPaths | None = None
) -> Preregistration:
    return preflight(
        prereg_path=paths["prereg"],
        model_path=paths["model"],
        lock_path=paths["lock"],
        catalog_path=paths["catalog"],
        git=git,
        phase="faz3",
        canonical=canonical,
    )


def test_preflight_passes_a_committed_matching_preregistration(tmp_path: Path) -> None:
    prereg = _preflight(_prereg_files(tmp_path), _git())

    assert prereg.comparisons == COMPARISONS and prereg.tau == 0.02


@pytest.mark.leakage
@pytest.mark.parametrize("change", ["dirty", "uncommitted", "model", "lock", "catalog", "phase"])
def test_preflight_refuses_before_anything_opens(tmp_path: Path, change: str) -> None:
    paths = _prereg_files(tmp_path)
    git = _git(clean=change != "dirty", committed=change != "uncommitted")
    if change in ("model", "lock", "catalog"):
        paths[change].write_text("değişti\n", encoding="utf-8")
    if change == "phase":
        text = paths["prereg"].read_text(encoding="utf-8").replace("phase: faz3", "phase: faz4")
        paths["prereg"].write_text(text, encoding="utf-8")

    with pytest.raises(PreflightError):
        _preflight(paths, git)


def test_a_malformed_preregistration_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "p.yaml"
    path.write_text("phase: faz3\n", encoding="utf-8")

    with pytest.raises(PreflightError, match="alanlar"):
        load_preregistration(path, phase="faz3")


@dataclass
class _Db:
    previous: list[tuple[str, str]] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)

    def __call__(self) -> _Db:
        self.calls.append("connect")
        return self

    def __enter__(self) -> _Db:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def cursor(self) -> _Db:
        return self

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        self.calls.append("count")

    def fetchall(self) -> list[tuple[str, str]]:
        return self.previous


def _patch(
    monkeypatch: pytest.MonkeyPatch, db: _Db, *, lock_error: bool = False, drop: int = 0
) -> None:
    def open_holdout(conn: object, *, purpose: str, git_sha: str, now: datetime) -> HoldoutKey:
        db.calls.append(f"open {purpose}")
        return HoldoutKey(opened_at=now, purpose=purpose, git_sha=git_sha)

    def load_matches(
        conn: object, catalog: object, *, lock: object = None, key: object = None
    ) -> object:
        db.calls.append("load keyed" if key is not None else "load")
        if lock_error and key is None:
            raise LockViolation("E0/holdout: fark")
        if key is None:
            return {"E0": tuple(m for m in EVERYTHING["E0"] if period_of(m.date) != HOLDOUT)}
        holdout = [m for m in EVERYTHING["E0"] if period_of(m.date) == HOLDOUT]
        return {"E0": tuple(m for m in EVERYTHING["E0"] if m not in holdout[:drop])}

    monkeypatch.setattr(final_eval, "open_holdout", open_holdout)
    monkeypatch.setattr(final_eval, "load_matches", load_matches)


def _run(db: _Db, tmp: Path, **kwargs: Any) -> Any:
    return run_final(
        db,  # type: ignore[arg-type]
        catalog=CATALOG,
        lock=LOCK,
        config=CONFIG,
        prereg=PREREG,
        prereg_sha256="p" * 64,
        git_sha=SHA,
        now=NOW,
        report_path=tmp / "rapor.md",
        **kwargs,
    )


@pytest.mark.leakage
def test_the_lock_is_verified_and_openings_counted_before_the_single_opening(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db = _Db()
    _patch(monkeypatch, db)

    report = _run(db, tmp_path)

    assert db.calls == [
        "connect",
        "load",
        "count",
        "connect",
        "open faz3:" + "p" * 64,
        "load keyed",
    ]
    assert report.holdout_rows == sum(1 for m in EVERYTHING["E0"] if period_of(m.date) == HOLDOUT)
    assert report.holdout.main and report.post.main


@pytest.mark.leakage
def test_a_previous_opening_stops_before_open(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db = _Db(previous=[("faz3:x", SHA)])
    _patch(monkeypatch, db)

    with pytest.raises(AlreadyOpened):
        _run(db, tmp_path)
    assert not any(call.startswith("open") for call in db.calls)


@pytest.mark.leakage
def test_a_lock_violation_stops_before_open(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db = _Db()
    _patch(monkeypatch, db, lock_error=True)

    with pytest.raises(LockViolation):
        _run(db, tmp_path)
    assert not any(call.startswith("open") for call in db.calls)


def test_a_holdout_count_that_differs_from_the_lock_fails_after_the_opening(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db = _Db()
    _patch(monkeypatch, db, drop=1)

    with pytest.raises(HoldoutCountMismatch) as raised:
        _run(db, tmp_path)
    assert isinstance(raised.value, OpenedButFailed)
    assert any(call.startswith("open") for call in db.calls)


def test_check_holdout_count_matches_the_lock() -> None:
    assert check_holdout_count(LOCK, EVERYTHING) == sum(
        1 for m in EVERYTHING["E0"] if period_of(m.date) == HOLDOUT
    )


def test_the_report_is_aggregate_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db = _Db()
    _patch(monkeypatch, db)

    text = render_final(_run(db, tmp_path), generated_at=NOW)

    assert "C1 ΔLL harman − piyasa" in text and "C6" in text and "Placebo" in text
    assert not any(team in text for team in TEAMS)


def test_the_phase_index_migration_allows_one_opening_and_one_rerun_per_phase() -> None:
    sql = (MIGRATIONS / "0010_holdout_phase.sql").read_text(encoding="utf-8")

    assert "create unique index if not exists holdout_access_log_one_per_phase" in sql
    assert "((split_part(purpose, ':', 1)))" in sql
    assert "where purpose ~ '^faz[0-9]+(-rerun)?:'" in sql


@pytest.mark.leakage
def test_the_rehearsal_runs_the_whole_path_without_opening(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _Db()
    _patch(monkeypatch, db)

    report = run_rehearsal(
        db,  # type: ignore[arg-type]
        catalog=CATALOG,
        lock=LOCK,
        config=CONFIG,
        prereg=PREREG,
        start=date(2024, 7, 1),
        end=date(2025, 7, 1),
    )

    assert db.calls == ["connect", "load"]
    assert report.purpose == "prova" and report.holdout_rows > 0
    assert report.holdout.main and not report.post.main


@pytest.mark.leakage
@pytest.mark.parametrize(
    ("failure", "code"),
    [("preflight", 12), ("duplicate", 12), ("already", 13), ("opened", 14), ("render", 14)],
)
def test_the_cli_names_where_it_stopped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, failure: str, code: int
) -> None:
    from football_edge.backtest import __main__ as cli

    paths = _prereg_files(tmp_path)
    monkeypatch.setattr(cli, "real_git", lambda: _git(clean=failure != "preflight"))
    monkeypatch.setattr(cli, "canonical_paths", lambda phase: _canonical(paths))
    monkeypatch.setattr(cli, "load_model_config", lambda path: CONFIG)
    monkeypatch.setattr(cli, "load_catalog", lambda path: CATALOG)
    monkeypatch.setattr(cli, "load_lock", lambda path: LOCK)

    def run_final(*args: object, **kwargs: object) -> object:
        if failure == "duplicate":
            from football_edge.history.sync import DuplicateMatches

            raise DuplicateMatches("yinelenen maç: E0 ×1")
        if failure == "render":
            return object()  # render_final bu nesneyle düşer: açıldı ama rapor yok
        raise AlreadyOpened("x") if failure == "already" else OpenedButFailed("y")

    monkeypatch.setattr(cli, "run_final", run_final)
    out = tmp_path / "rapor.md"

    returned = cli.main(
        [
            "final-eval",
            "--phase",
            "faz3",
            "--prereg",
            str(paths["prereg"]),
            "--config",
            str(paths["model"]),
            "--lock",
            str(paths["lock"]),
            "--catalog",
            str(paths["catalog"]),
            "--out",
            str(out),
        ]
    )

    assert returned == code and not out.exists()


@pytest.mark.leakage
def test_a_duplicate_found_by_the_keyless_load_stops_before_open(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """C1: bütün dönemlerdeki yineleme reddi açılıştan önce gelir; CLI onu exit 12 sayar."""
    from football_edge.history.sync import DuplicateMatches

    db = _Db()
    _patch(monkeypatch, db)

    def refusing(
        conn: object, catalog: object, *, lock: object = None, key: object = None
    ) -> object:
        db.calls.append("load")
        raise DuplicateMatches("football-data: yinelenen maç (bütün dönemler, 14g): E0 ×1")

    monkeypatch.setattr(final_eval, "load_matches", refusing)

    with pytest.raises(DuplicateMatches):
        _run(db, tmp_path)
    assert not any(call.startswith("open") for call in db.calls)


@pytest.mark.leakage
def test_any_failure_after_the_opening_is_reported_as_opened(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """I4: açılış kayda düştükten sonraki her arıza exit 14 sınıfıdır (yeniden koşu ona bakar)."""
    db = _Db()
    _patch(monkeypatch, db)

    def broken(*args: object, **kwargs: object) -> object:
        raise RuntimeError("değerlendirme çöktü")

    monkeypatch.setattr(final_eval, "evaluate_selected", broken)

    with pytest.raises(OpenedButFailed, match="RuntimeError"):
        _run(db, tmp_path)
    assert any(call.startswith("open") for call in db.calls)


def test_the_phase_index_rejecting_the_insert_is_not_an_opening(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """I4: 0010'un `UniqueViolation`ı INSERT'i geri alır — açılış yok, exit 13 sınıfı."""
    import psycopg

    db = _Db()
    _patch(monkeypatch, db)

    def rejected(conn: object, *, purpose: str, git_sha: str, now: datetime) -> HoldoutKey:
        raise psycopg.errors.UniqueViolation("holdout_access_log_one_per_phase")

    monkeypatch.setattr(final_eval, "open_holdout", rejected)

    with pytest.raises(AlreadyOpened, match="0010"):
        _run(db, tmp_path)
    assert "load keyed" not in db.calls


@pytest.mark.leakage
def test_a_logged_rerun_reaches_open_holdout_with_its_purpose(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """R135: yeniden koşunun amacı (`faz3-rerun:<neden>:<sha>`) açılışa aynen ulaşır."""
    db = _Db(previous=[("faz3:" + "p" * 64, SHA)])
    _patch(monkeypatch, db)

    _run(db, tmp_path, rerun_reason="OOM")

    assert "open faz3-rerun:OOM:" + "p" * 64 in db.calls


class _DroppingDb(_Db):
    """Açılıştan sonra bağlantının kapanışı (`__exit__` → commit) düşer."""

    def __exit__(self, *exc: object) -> None:
        import psycopg

        if any(call.startswith("open") for call in self.calls):
            raise psycopg.OperationalError("bağlantı koptu")


@pytest.mark.leakage
def test_a_connection_dropping_after_the_opening_is_reported_as_opened(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """P15: açılış kayda düştükten sonra bağlantı kapanışında düşmek de exit 14 sınıfıdır."""
    db = _DroppingDb()
    _patch(monkeypatch, db)

    with pytest.raises(OpenedButFailed, match="OperationalError"):
        _run(db, tmp_path)
    assert any(call.startswith("open") for call in db.calls)


@pytest.mark.leakage
def test_the_cli_rehearsal_writes_its_report_without_trying_the_opening(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """P22: `--rehearse` yalnız `run_rehearsal`ı çağırır; `run_final`e hiç girmez."""
    from football_edge.backtest import __main__ as cli

    paths = _prereg_files(tmp_path)
    monkeypatch.setattr(cli, "real_git", lambda: _git())
    monkeypatch.setattr(cli, "load_model_config", lambda path: CONFIG)
    monkeypatch.setattr(cli, "load_catalog", lambda path: CATALOG)
    monkeypatch.setattr(cli, "load_lock", lambda path: LOCK)
    rehearsed: list[str] = []

    def run_rehearsal(*args: object, **kwargs: object) -> object:
        rehearsed.append("prova")
        return object()

    def run_final(*args: object, **kwargs: object) -> object:
        raise AssertionError("açılış denendi")

    monkeypatch.setattr(cli, "run_rehearsal", run_rehearsal)
    monkeypatch.setattr(cli, "run_final", run_final)
    monkeypatch.setattr(cli, "render_final", lambda report, *, generated_at: "prova raporu\n")
    out = tmp_path / "prova.md"

    returned = cli.main(
        [
            "final-eval",
            "--phase",
            "faz3",
            "--rehearse",
            "--prereg",
            str(paths["prereg"]),
            "--config",
            str(paths["model"]),
            "--lock",
            str(paths["lock"]),
            "--catalog",
            str(paths["catalog"]),
            "--out",
            str(out),
        ]
    )

    assert returned == 0 and rehearsed == ["prova"]
    assert out.read_text(encoding="utf-8") == "prova raporu\n"


# ── 16b/16d: faz parametresi ve kanonik yollar ──────────────────────────────────────────────


def test_the_committed_faz3_preregistration_still_loads_from_its_canonical_path() -> None:
    from football_edge.backtest import __main__ as cli

    canonical = cli.canonical_paths("faz3")

    prereg = load_preregistration(REPO / canonical.prereg, phase="faz3")

    assert prereg.phase == "faz3" and prereg.comparisons == COMPARISONS
    assert canonical.model == MODEL_CONFIG_PATH
    assert (canonical.lock, canonical.catalog) == (cli.LOCK_PATH, cli.CATALOG_PATH)
    assert all((REPO / path).is_file() for path in vars(canonical).values())


def test_an_unknown_phase_is_refused_before_the_file_is_read(tmp_path: Path) -> None:
    with pytest.raises(PreflightError, match="bilinmeyen faz"):
        load_preregistration(tmp_path / "yok.yaml", phase="faz9")


def test_the_purpose_carries_the_phase() -> None:
    first = purpose_for(
        (), phase="faz4", prereg_sha256="p", git_sha=SHA, report_exists=False, rerun_reason=None
    )
    rerun = purpose_for(
        (("faz4:p", SHA),),
        phase="faz4",
        prereg_sha256="p",
        git_sha=SHA,
        report_exists=False,
        rerun_reason="OOM",
    )

    assert (first, rerun) == ("faz4:p", "faz4-rerun:OOM:p")


class _Log:
    """`holdout_access_log` okuyucusu: SQL'in süzgecini (0010'un ifadesi) Python'da uygular."""

    def __init__(self, purposes: list[str]) -> None:
        self.purposes = purposes
        self.params: tuple[Any, ...] = ()

    def cursor(self) -> _Log:
        return self

    def __enter__(self) -> _Log:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        assert "split_part(purpose, ':', 1) IN (%s, %s)" in sql
        self.params = params

    def fetchall(self) -> list[tuple[str, str]]:
        return [(p, SHA) for p in self.purposes if p.split(":", 1)[0] in self.params]


@pytest.mark.leakage
def test_previous_openings_count_only_the_exact_phase_and_its_rerun() -> None:
    """16d: `LIKE 'faz3%'` `faz30`u da sayardı; sayım fazın TAM adıdır."""
    log = _Log(["faz3:a", "faz3-rerun:OOM:a", "faz30:b", "faz3x:c", "faz4:d", "prova"])

    found = previous_openings(log, phase="faz3")  # type: ignore[arg-type]

    assert found == (("faz3:a", SHA), ("faz3-rerun:OOM:a", SHA))
    assert log.params == ("faz3", "faz3-rerun")


@pytest.mark.leakage
@pytest.mark.parametrize("name", ["prereg", "model", "lock", "catalog"])
def test_a_real_opening_refuses_a_path_that_is_not_canonical(tmp_path: Path, name: str) -> None:
    """16b: commit'li başka bir dosya ön kayıt, model, kilit ya da katalog yerine geçemez."""
    paths = _prereg_files(tmp_path)
    canonical = replace(_canonical(paths), **{name: tmp_path / "kanonik" / f"{name}.yaml"})

    with pytest.raises(PreflightError, match="kanonik yolda değil"):
        _preflight(paths, _git(), canonical)


@pytest.mark.leakage
def test_the_cli_refuses_a_real_opening_from_non_canonical_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """16b: kanonik olmayan yolla gerçek açılış exit 12; `run_final`e hiç girilmez.

    Yükleyiciler saplanır: exit 12 yalnız kanonik yol denetiminden gelebilir, bozuk bir test
    dosyasının `ModelConfigError`ından değil (review Task 3, M3 `canonical=None`).
    """
    from football_edge.backtest import __main__ as cli

    paths = _prereg_files(tmp_path)
    monkeypatch.setattr(cli, "real_git", lambda: _git())
    monkeypatch.setattr(cli, "load_model_config", lambda path: CONFIG)
    monkeypatch.setattr(cli, "load_catalog", lambda path: CATALOG)
    monkeypatch.setattr(cli, "load_lock", lambda path: LOCK)

    def run_final(*args: object, **kwargs: object) -> object:
        raise AssertionError("açılış denendi")

    monkeypatch.setattr(cli, "run_final", run_final)
    out = tmp_path / "rapor.md"

    returned = cli.main(
        [
            "final-eval",
            "--phase",
            "faz3",
            "--prereg",
            str(paths["prereg"]),
            "--config",
            str(paths["model"]),
            "--lock",
            str(paths["lock"]),
            "--catalog",
            str(paths["catalog"]),
            "--out",
            str(out),
        ]
    )

    assert returned == 12 and not out.exists()
    assert "kanonik yolda değil" in caplog.text


def test_a_canonical_path_spelled_another_way_is_the_same_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Review Focus (16b): `./x`, göreli ve mutlak yazım aynı dosyadır — operatör exit 12 almaz."""
    paths = _prereg_files(tmp_path)
    monkeypatch.chdir(tmp_path)
    canonical = CanonicalPaths(
        prereg=Path("prereg.yaml"),
        model=Path("./model.yaml"),
        lock=tmp_path / "lock.yaml",
        catalog=Path(".") / "catalog.yaml",
    )

    assert _preflight(paths, _git(), canonical).phase == "faz3"


# ── 16a: rapor yolu açılıştan ÖNCE · 16c: rapor ortak kümeyi ve eşleştirilmiş ΔLL'yi basar ──


def test_a_writable_report_path_passes_the_probe_without_writing(tmp_path: Path) -> None:
    probe_out_dir(tmp_path / "rapor.md")

    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("where", "message"),
    [("missing", "dizini yok"), ("directory", "bir dizin"), ("read-only", "yazılamaz")],
)
def test_an_unusable_report_path_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, where: str, message: str
) -> None:
    path = {
        "missing": tmp_path / "yok" / "rapor.md",
        "directory": tmp_path,
        "read-only": tmp_path / "rapor.md",
    }[where]
    if where == "read-only":
        monkeypatch.setattr(os, "access", lambda path, mode: False)

    with pytest.raises(PreflightError, match=message):
        probe_out_dir(path)


@pytest.mark.leakage
def test_the_cli_probes_the_report_path_before_the_opening(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """16a: yazılamayan `--out` açılıştan SONRA exit 14'tü; şimdi açılıştan ÖNCE exit 12."""
    from football_edge.backtest import __main__ as cli

    paths = _prereg_files(tmp_path)
    monkeypatch.setattr(cli, "real_git", lambda: _git())
    monkeypatch.setattr(cli, "canonical_paths", lambda phase: _canonical(paths))
    monkeypatch.setattr(cli, "load_model_config", lambda path: CONFIG)

    def run_final(*args: object, **kwargs: object) -> object:
        raise AssertionError("açılış denendi")

    monkeypatch.setattr(cli, "run_final", run_final)

    returned = cli.main(
        [
            "final-eval",
            "--phase",
            "faz3",
            "--prereg",
            str(paths["prereg"]),
            "--config",
            str(paths["model"]),
            "--lock",
            str(paths["lock"]),
            "--catalog",
            str(paths["catalog"]),
            "--out",
            str(tmp_path / "yok" / "rapor.md"),
        ]
    )

    assert returned == 12


def test_the_report_prints_paired_gaps_incomplete_rows_and_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db = _Db()
    _patch(monkeypatch, db)
    report = _run(db, tmp_path)

    text = render_final(report, generated_at=NOW)

    for name in report.holdout.component_gaps:
        assert f"C2 ΔLL {name} − piyasa: " in text
    assert set(report.holdout.component_gaps) == {"dixon_coles", "elo_fit", "elo_scaffold"}
    assert "C5 ΔLL dixon_coles − piyasa (Ü/A 2.5): " in text
    assert f"bileşeni eksik (ortak kümeye girmedi) {report.holdout.incomplete}" in text
    fallback = ", ".join(report.holdout.fallback)
    assert report.holdout.fallback and f"({fallback})" in text


def test_a_bare_or_already_written_report_path_passes_the_probe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Review Focus (16a): `--out rapor.md` (üst dizin `.`) ve var olan rapor (yeniden koşunun
    `report_exists` denetimi onu görmeli) yoklamada reddedilmez."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "eski.md").write_text("önceki rapor\n", encoding="utf-8")

    probe_out_dir(Path("rapor.md"))
    probe_out_dir(tmp_path / "eski.md")


def test_the_report_renders_when_a_zone_has_no_common_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review Focus (16c): provada sonrası dönemi boştur; yeni satırlar (C2, C5, kapsam) orada da
    basılmalı — gerçek açılışta render çökerse holdout harcanır ve rapor yoktur (exit 14)."""
    db = _Db()
    _patch(monkeypatch, db)
    report = run_rehearsal(
        db,  # type: ignore[arg-type]
        catalog=CATALOG,
        lock=LOCK,
        config=CONFIG,
        prereg=PREREG,
        start=date(2024, 7, 1),
        end=date(2025, 7, 1),
    )

    text = render_final(report, generated_at=NOW)

    assert not report.post.main and report.post.component_gaps == {}
    assert "C6 ΔLL harman − piyasa: ölçülemedi" in text
    assert "Sonrası: satır 0 · bileşeni eksik (ortak kümeye girmedi) 0" in text


def test_the_report_names_why_matches_left_the_common_rows_and_counts_refused_prices(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """16p ve 16i: holdout'un satırsız/eksik maçları ve reddedilen fiyatları raporda adıyla."""
    db = _Db()
    _patch(monkeypatch, db)
    report = _run(db, tmp_path)

    text = render_final(report, generated_at=NOW)

    for zone, label in ((HOLDOUT, "Holdout"), (POST, "Sonrası")):
        assert tuple(report.missing[zone]) == MISSING_REASONS
        assert f"{label}, ortak kümeye girmeyen ana lig maçı: " in text
        assert format_counts(report.missing[zone]) in text
        assert format_counts(report.rejected[zone]) in text
