"""M1/M7/R50 — `fetch-footystats`/`fetch-tff`/`fetch-venues`/`fetch-news`/`fetch-results`
kablolaması.

Bu dosya DAĞITIM (dispatch) katmanını sınar: doğru toplayıcı fonksiyon çağrılıyor mu,
sonuç doğru satırlarla raporlanıyor mu, doğru çıkış kodu dönüyor mu. Toplayıcıların
KENDİ mantığı (izolasyon, UTC dönüşümü, M6 kararı, ...) zaten `tests/test_venues.py`,
`tests/test_news.py`, `tests/test_results.py`de kanıtlanmış — burada TEKRAR edilmez.

R50 (Task 11): beş `_fetch_*_command` fonksiyonu `collect.py`den `fetch.py`ye taşındı
(collect.py 774/800 satırdaydı, #M41). `fetch.*` fonksiyonları monkeypatch'lenir (aynı
desen: `test_collect_main.py::test_main_spends_no_credit_when_the_league_mirror_fails`)
— ama artık `collect` DEĞİL `fetch` modülünün namespace'inde, çünkü taşınan fonksiyonlar
serbest değişkenlerini KENDİ tanımlandıkları modülün globals'ından çözer. `main()` hâlâ
`collect.py`de yaşıyor ve `connect()`i hâlâ oradan çağırıyor — o yüzden "uçtan uca"
testler `collect.main(...)`i çağırmaya, `collect.connect`i yamalamaya devam ediyor.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from football_edge import collect, fetch
from football_edge.collectors.footystats import FootyStatsResult
from football_edge.collectors.news import NewsCollectResult
from football_edge.collectors.results import ResultsCollectResult
from football_edge.collectors.venues import VenuesResult
from football_edge.leagues import League
from tests.fake_db import FakeLedgerDb

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


class _RollbackCountingConn:
    def __init__(self) -> None:
        self.rollbacks = 0

    def rollback(self) -> None:
        self.rollbacks += 1


# ---------------------------------------------------------------------------
# fetch-footystats — R50 öncesi `main()` içine gömülüydü, hiç doğrudan test
# edilmemişti (yalnız `collectors/test_footystats.py` ayrıştırıcıyı sınıyordu).
# Taşıma bu boşluğu görünür kıldı; kardeşleriyle aynı desende iki test eklendi.
# ---------------------------------------------------------------------------


def test_fetch_footystats_command_reports_written_count_and_returns_zero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        fetch, "collect_footystats", lambda *a, **k: FootyStatsResult(written=6, failed_leagues=())
    )

    code = fetch._fetch_footystats_command(object(), object(), NOW)

    out = capsys.readouterr().out
    assert code == 0
    assert "footystats: 6 yeni gözlem" in out
    assert "başarısız" not in out


def test_fetch_footystats_command_names_failed_leagues_and_returns_exit_league_failed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        fetch,
        "collect_footystats",
        lambda *a, **k: FootyStatsResult(written=2, failed_leagues=("tur.1",)),
    )

    code = fetch._fetch_footystats_command(object(), object(), NOW)

    out = capsys.readouterr().out
    assert code == collect.EXIT_LEAGUE_FAILED
    assert "footystats başarısız ligler: tur.1" in out


# ---------------------------------------------------------------------------
# fetch-tff
# ---------------------------------------------------------------------------


def test_fetch_tff_command_reports_written_count_and_returns_zero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(fetch, "collect_tff", lambda *a, **k: 7)

    code = fetch._fetch_tff_command(object(), object(), NOW)

    out = capsys.readouterr().out
    assert code == 0
    assert "tff: 7 yeni gözlem" in out


def test_fetch_tff_command_rolls_back_and_returns_exit_source_failed_on_exception(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def boom(*args: object, **kwargs: object) -> int:
        raise RuntimeError("tff sayfası çekilemedi")

    monkeypatch.setattr(fetch, "collect_tff", boom)
    conn = _RollbackCountingConn()

    code = fetch._fetch_tff_command(conn, object(), NOW)  # type: ignore[arg-type]

    out = capsys.readouterr().out
    assert code == collect.EXIT_SOURCE_FAILED
    assert conn.rollbacks == 1
    assert "tff" in out and "başarısız" in out


# ---------------------------------------------------------------------------
# fetch-venues
# ---------------------------------------------------------------------------


def test_fetch_venues_command_reports_written_and_returns_zero_when_nothing_failed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        fetch,
        "collect_venues",
        lambda *a, **k: VenuesResult(written=3, failed_venues=(), failed_matches=()),
    )

    code = fetch._fetch_venues_command(object(), object(), NOW)

    out = capsys.readouterr().out
    assert code == 0
    assert "venues: 3 yeni gözlem" in out
    assert "başarısız" not in out


def test_fetch_venues_command_names_failed_venues_and_matches_and_returns_exit_source_failed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        fetch,
        "collect_venues",
        lambda *a, **k: VenuesResult(
            written=1, failed_venues=("Q81492",), failed_matches=("evt-bad",)
        ),
    )

    code = fetch._fetch_venues_command(object(), object(), NOW)

    out = capsys.readouterr().out
    assert code == collect.EXIT_SOURCE_FAILED
    assert "venues başarısız stadyumlar: Q81492" in out
    assert "venues başarısız maçlar (hava): evt-bad" in out


# ---------------------------------------------------------------------------
# fetch-news
# ---------------------------------------------------------------------------


def test_fetch_news_command_reports_self_stamped_count_without_failing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """M6: kendi-damgalı öğe sayısı BAŞARILI bir turda da adıyla raporlanır — sessiz kalmaz."""
    monkeypatch.setattr(
        fetch,
        "collect_news",
        lambda *a, **k: NewsCollectResult(written=5, self_stamped=2, failed_sources=()),
    )

    code = fetch._fetch_news_command(object(), object(), NOW)

    out = capsys.readouterr().out
    assert code == 0
    assert "news: 5 yeni gözlem" in out
    assert "news kendi-damgalı (tazelik denetlenmedi): 2" in out


def test_fetch_news_command_names_failed_sources_and_returns_exit_source_failed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        fetch,
        "collect_news",
        lambda *a, **k: NewsCollectResult(written=0, self_stamped=0, failed_sources=("ajansspor",)),
    )

    code = fetch._fetch_news_command(object(), object(), NOW)

    out = capsys.readouterr().out
    assert code == collect.EXIT_SOURCE_FAILED
    assert "news başarısız kaynaklar: ajansspor" in out


# ---------------------------------------------------------------------------
# fetch-results
# ---------------------------------------------------------------------------


def test_fetch_results_command_reports_scoreless_and_returns_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    leagues_path = tmp_path / "leagues.yaml"
    leagues_path.write_text(
        "leagues:\n"
        "  - id: good.1\n"
        "    odds_api_key: soccer_good\n"
        "    name: Good\n"
        "    country: X\n"
        "    lang: en\n"
        "    gl: GB\n"
        "    active: true\n"
        "    footystats_path: /good/xg\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(fetch, "LEAGUES_PATH", leagues_path)
    monkeypatch.setenv("ODDS_API_KEY", "TEST-KEY")
    seen_leagues: list[tuple[str, ...]] = []

    def fake_collect_results(
        conn: object, client: object, api_key: str, leagues: tuple[League, ...], now: object
    ) -> ResultsCollectResult:
        seen_leagues.append(tuple(league.id for league in leagues))
        assert api_key == "TEST-KEY"
        return ResultsCollectResult(written=2, failed_leagues=(), scoreless_completed=("evt9",))

    monkeypatch.setattr(fetch, "collect_results", fake_collect_results)

    code = fetch._fetch_results_command(object(), object(), NOW)

    out = capsys.readouterr().out
    assert code == 0
    assert seen_leagues == [("good.1",)]
    assert "results: 2 yeni sonuç" in out
    assert "results tamamlanmış ama skorsuz: evt9" in out


def test_fetch_results_command_reuses_exit_league_failed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """M7 kararı: `fetch-results` GERÇEKTEN lig döngüler — `EXIT_LEAGUE_FAILED`ı DOĞRU
    biçimde yeniden kullanır, `EXIT_SOURCE_FAILED` ALMAZ (bkz. fetch.py'deki yorum)."""
    leagues_path = tmp_path / "leagues.yaml"
    leagues_path.write_text("leagues: []\n", encoding="utf-8")
    monkeypatch.setattr(fetch, "LEAGUES_PATH", leagues_path)
    monkeypatch.setenv("ODDS_API_KEY", "TEST-KEY")
    monkeypatch.setattr(
        fetch,
        "collect_results",
        lambda *a, **k: ResultsCollectResult(
            written=0, failed_leagues=("bad.1",), scoreless_completed=()
        ),
    )

    code = fetch._fetch_results_command(object(), object(), NOW)

    out = capsys.readouterr().out
    assert code == collect.EXIT_LEAGUE_FAILED
    assert code != collect.EXIT_SOURCE_FAILED
    assert "results başarısız ligler: bad.1" in out


def test_fetch_results_command_requires_odds_api_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    leagues_path = tmp_path / "leagues.yaml"
    leagues_path.write_text("leagues: []\n", encoding="utf-8")
    monkeypatch.setattr(fetch, "LEAGUES_PATH", leagues_path)
    monkeypatch.delenv("ODDS_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="ODDS_API_KEY"):
        fetch._fetch_results_command(object(), object(), NOW)


# ---------------------------------------------------------------------------
# main() uçtan uca — argparse `choices`e kayıt oldukları ve `connect()`/`httpx.Client()`
# kablolamasından GERÇEKTEN geçtiği (yalnız izole fonksiyon çağrısı değil).
# ---------------------------------------------------------------------------


def test_main_routes_fetch_footystats_end_to_end(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """R50: footystats artık inline değil, `fetch._fetch_footystats_command`."""
    db = FakeLedgerDb()
    leagues_path = tmp_path / "leagues.yaml"
    leagues_path.write_text("leagues: []\n", encoding="utf-8")
    monkeypatch.setattr(collect, "connect", lambda: db)
    monkeypatch.setattr(fetch, "LEAGUES_PATH", leagues_path)
    monkeypatch.setattr(
        fetch, "collect_footystats", lambda *a, **k: FootyStatsResult(written=6, failed_leagues=())
    )

    code = collect.main(["fetch-footystats"])

    out = capsys.readouterr().out
    assert code == 0
    assert "footystats: 6 yeni gözlem" in out


def test_main_routes_fetch_tff_end_to_end(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db = FakeLedgerDb()
    monkeypatch.setattr(collect, "connect", lambda: db)
    monkeypatch.setattr(fetch, "collect_tff", lambda *a, **k: 4)

    code = collect.main(["fetch-tff"])

    out = capsys.readouterr().out
    assert code == 0
    assert "tff: 4 yeni gözlem" in out


def test_main_routes_fetch_venues_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    db = FakeLedgerDb()
    monkeypatch.setattr(collect, "connect", lambda: db)
    monkeypatch.setattr(fetch, "collect_venues", lambda *a, **k: VenuesResult(written=0))

    assert collect.main(["fetch-venues"]) == 0


def test_main_routes_fetch_news_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    db = FakeLedgerDb()
    monkeypatch.setattr(collect, "connect", lambda: db)
    monkeypatch.setattr(fetch, "collect_news", lambda *a, **k: NewsCollectResult(written=0))

    assert collect.main(["fetch-news"]) == 0


def test_main_routes_fetch_results_end_to_end(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db = FakeLedgerDb()
    leagues_path = tmp_path / "leagues.yaml"
    leagues_path.write_text("leagues: []\n", encoding="utf-8")
    monkeypatch.setattr(collect, "connect", lambda: db)
    monkeypatch.setattr(fetch, "LEAGUES_PATH", leagues_path)
    monkeypatch.setenv("ODDS_API_KEY", "TEST-KEY")
    monkeypatch.setattr(fetch, "collect_results", lambda *a, **k: ResultsCollectResult(written=0))

    assert collect.main(["fetch-results"]) == 0


def test_there_is_deliberately_no_elo_subcommand() -> None:
    """`football_edge.elo` toplamaz/yazmaz — Faz 2 kendi harness'inden çağıracak."""
    with pytest.raises(SystemExit):
        collect.main(["elo"])
