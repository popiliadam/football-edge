"""Task 11 — `map-entities` CLI kablolaması.

Bu dosya DAĞITIM katmanını sınar (aynı desen: `test_collect_fetch_commands.py`):
`mapping.canonical_team_names`/`mapping.resolve_source_aliases` `collect.*` üzerinden
monkeypatch'lenir. KENDİ mantıkları (lig önekine göre süzme, eşik, yazma) zaten
`tests/test_mapping.py`de kanıtlanmış — burada TEKRAR edilmez; burada sınanan yalnız
"doğru kolaborasyon doğru argümanla çağrılıyor mu, rapor/çıkış kodu doğru mu".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from football_edge import collect
from football_edge.mapping import MappingReport, Resolution

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def _explode(*_a: object, **_k: object) -> object:
    raise AssertionError("bu kolaborasyon ÇAĞRILMAMALIYDI")


@dataclass
class _NullConn:
    """`connect()`in yerini tutar; hiçbir yolda gerçekten sorgulanmaz (her kolaborasyon
    monkeypatch'li), yalnız `with connect() as conn:` biçiminin çalışması için var."""

    closed: bool = field(default=False)

    def __enter__(self) -> _NullConn:
        return self

    def __exit__(self, *exc: object) -> None:
        self.closed = True


# ---------------------------------------------------------------------------
# _map_entities_command
# ---------------------------------------------------------------------------


def test_map_entities_command_reports_written_and_unresolved_counts(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(collect, "canonical_team_names", lambda conn, league: ("Galatasaray",))
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    resolved = Resolution("Galatasaray Istanbul", "Galatasaray", 0.9, "model seçti")
    unresolved = Resolution("Panathinaikos", None, 0.99, "model 'hiçbiri' dedi")
    monkeypatch.setattr(
        collect,
        "resolve_source_aliases",
        lambda conn, client, source, league, canonical, now: MappingReport(
            written=1, resolutions=(resolved, unresolved)
        ),
    )

    code = collect._map_entities_command(object(), "footystats", "tur.1", NOW)

    out = capsys.readouterr().out
    assert code == 0
    assert "1 eşleşme yazıldı, 1 çözülmedi" in out
    assert "çözülmedi: 'Panathinaikos' — model 'hiçbiri' dedi" in out
    assert "Galatasaray Istanbul" not in out, "çözülen alias adıyla raporlanmamalı — gürültü olur"


def test_map_entities_command_passes_source_league_and_canonical_through(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(collect, "canonical_team_names", lambda conn, league: ("Galatasaray",))
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    seen: list[tuple[object, ...]] = []

    def fake_resolve_source_aliases(
        conn: object,
        client: object,
        source: str,
        league: str,
        canonical: tuple[str, ...],
        now: object,
    ) -> MappingReport | None:
        seen.append((source, league, canonical, now))
        return None

    monkeypatch.setattr(collect, "resolve_source_aliases", fake_resolve_source_aliases)

    collect._map_entities_command(object(), "footystats", "tur.1", NOW)

    assert seen == [("footystats", "tur.1", ("Galatasaray",), NOW)]


def test_map_entities_command_stops_before_constructing_jev_when_no_canonical_teams(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Kanonik liste boşsa (bu lig `matches`te hiç yok) Jev KURULMAZ, `resolve_source_
    aliases` hiç ÇAĞRILMAZ — boş bir turda bile `TYPESAFE_API_KEY` istemek gereksizdir."""
    monkeypatch.setattr(collect, "canonical_team_names", lambda conn, league: ())
    monkeypatch.setattr(collect, "TypeSafeJev", _explode)
    monkeypatch.setattr(collect, "resolve_source_aliases", _explode)

    code = collect._map_entities_command(object(), "footystats", "tur.9", NOW)

    out = capsys.readouterr().out
    assert code == 0
    assert "tur.9 için matches tablosunda takım yok" in out


def test_map_entities_command_reports_no_observations_when_nothing_matched_the_league(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`resolve_source_aliases` `None` dönerse (bu ligde hiç gözlem yok) adıyla raporlanır."""
    monkeypatch.setattr(collect, "canonical_team_names", lambda conn, league: ("Galatasaray",))
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setattr(collect, "resolve_source_aliases", lambda *a, **k: None)

    code = collect._map_entities_command(object(), "footystats", "tur.1", NOW)

    out = capsys.readouterr().out
    assert code == 0
    assert "footystats/tur.1 için gözlem yok" in out


def test_map_entities_command_requires_typesafe_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anahtarsız SESSİZCE geçmez: `TypeSafeJev()` adıyla patlar (brief'in prerequisite-gap
    talimatı) — canlı bir çağrı asla denenmez, kurulum hatası hemen görünür olur."""
    monkeypatch.setattr(collect, "canonical_team_names", lambda conn, league: ("Galatasaray",))
    monkeypatch.setattr(collect, "resolve_source_aliases", _explode)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="TYPESAFE_API_KEY"):
        collect._map_entities_command(object(), "footystats", "tur.1", NOW)


# ---------------------------------------------------------------------------
# main() kablolaması — argparse `choices`, `--league` zorunluluğu.
# ---------------------------------------------------------------------------


def test_main_rejects_map_entities_without_a_league(capsys: pytest.CaptureFixture[str]) -> None:
    """Lig TAHMİN EDİLMEZ: aynı ad farklı ligde farklı kulüp olabilir."""
    with pytest.raises(SystemExit) as exc_info:
        collect.main(["map-entities"])

    assert exc_info.value.code == 2
    assert "--league" in capsys.readouterr().err


def test_main_routes_map_entities_end_to_end(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(collect, "connect", lambda: _NullConn())
    monkeypatch.setattr(collect, "canonical_team_names", lambda conn, league: ())

    code = collect.main(["map-entities", "--league", "tur.1"])

    out = capsys.readouterr().out
    assert code == 0
    assert "tur.1 için matches tablosunda takım yok" in out


def test_main_routes_map_entities_with_explicit_source(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: list[str] = []
    monkeypatch.setattr(collect, "connect", lambda: _NullConn())

    def fake_canonical(conn: object, league: str) -> tuple[str, ...]:
        seen.append(league)
        return ()

    monkeypatch.setattr(collect, "canonical_team_names", fake_canonical)

    code = collect.main(["map-entities", "--source", "tff", "--league", "tur.1"])

    assert code == 0
    assert seen == ["tur.1"]


def test_main_defaults_the_source_to_footystats(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(collect, "connect", lambda: _NullConn())
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setattr(collect, "canonical_team_names", lambda conn, league: ("Galatasaray",))
    seen: list[str] = []
    monkeypatch.setattr(
        collect,
        "resolve_source_aliases",
        lambda conn, client, source, league, canonical, now: (seen.append(source), None)[1],
    )

    collect.main(["map-entities", "--league", "tur.1"])

    assert seen == ["footystats"]
