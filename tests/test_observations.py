from __future__ import annotations

from datetime import UTC, datetime, timedelta

from football_edge.collector import Observation
from football_edge.observations import latest_observations, write_observations
from tests.fake_obs_db import FakeObservationDb

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def obs(key: str, xg: float) -> Observation:
    return Observation("footystats", "team", key, NOW, {"xg": xg})


def test_writes_every_new_observation() -> None:
    db = FakeObservationDb()
    assert write_observations(db, (obs("gs", 1.5), obs("fb", 1.2))) == 2


def test_identical_content_is_not_written_twice() -> None:
    """Aynı tablo her turda yeniden gözlenir; depo idempotent olmalı, yoksa sınırsız büyür."""
    db = FakeObservationDb()
    write_observations(db, (obs("gs", 1.5),))
    assert write_observations(db, (obs("gs", 1.5),)) == 0
    assert write_observations(db, (obs("gs", 1.6),)) == 1


def test_writes_use_a_single_statement() -> None:
    db = FakeObservationDb()
    write_observations(db, tuple(obs(f"t{i}", 1.0 + i / 10) for i in range(40)))
    inserts = [s for s in db.statements if s.startswith("INSERT INTO source_observations")]
    assert len(inserts) == 1


def test_latest_observations_returns_the_newest_row_per_entity_key() -> None:
    """`write_observations` her turda YENİ satır ekler; okuma tarafı entity_key başına
    yalnız EN YENİYİ dönmeli — aksi hâlde aynı takımın eski ve yeni gözlemi birlikte
    görünür ve okuyan hangisinin güncel olduğunu bilemez."""
    db = FakeObservationDb()
    write_observations(db, (obs("gs", 1.2),))
    newer = Observation("footystats", "team", "gs", NOW + timedelta(hours=2), {"xg": 1.9})
    write_observations(db, (newer,))
    write_observations(db, (obs("fb", 1.0),))

    result = latest_observations(db, "footystats", "team")

    by_key = {entry.entity_key: entry for entry in result}
    assert set(by_key) == {"gs", "fb"}
    assert by_key["gs"].payload["xg"] == 1.9
    assert by_key["gs"].observed_at == newer.observed_at


def test_latest_observations_is_scoped_to_source_and_entity_kind() -> None:
    """`source_id`/`entity_kind` filtresi düşerse başka kaynağın ya da başka varlık
    türünün gözlemi sessizce karışır — bu test tam o karışmayı yakalar."""
    db = FakeObservationDb()
    write_observations(db, (obs("gs", 1.5),))
    write_observations(db, (Observation("understat", "team", "gs", NOW, {"xg": 9.9}),))
    write_observations(db, (Observation("footystats", "player", "gs", NOW, {"xg": 9.9}),))

    result = latest_observations(db, "footystats", "team")

    assert len(result) == 1
    assert result[0].payload["xg"] == 1.5
