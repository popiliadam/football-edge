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


def _latest_select(db: FakeObservationDb) -> str:
    """Tam olarak bir `latest_observations` SELECT'i bekler; yoksa test yanlış şeyi ölçer."""
    selects = [s for s in db.statements if s.startswith("SELECT DISTINCT ON (entity_key)")]
    assert len(selects) == 1, f"beklenen tek SELECT, gelen: {selects}"
    return selects[0]


def test_latest_observations_returns_the_newest_row_per_entity_key() -> None:
    """`write_observations` her turda YENİ satır ekler; okuma tarafı entity_key başına
    yalnız EN YENİYİ dönmeli — aksi hâlde aynı takımın eski ve yeni gözlemi birlikte
    görünür ve okuyan hangisinin güncel olduğunu bilemez.

    Review #6, ÖLÇÜLDÜ: `tests/fake_obs_db.py`nin `_execute_latest`i "en yeniyi tut"
    mantığını KENDİ Python koduyla uyguluyor, gönderilen SQL METNİNDEN BAĞIMSIZ — yani
    `observations.py`deki `ORDER BY entity_key, observed_at DESC` `ASC`ye çevrilse bile
    yalnız aşağıdaki davranış-temelli iddialar YEŞİL kalırdı (reviewer'ın kendisi
    `observations.py:40`ı değiştirip doğruladı). Bu yüzden gerçek sorgu METNİ de AYRICA
    doğrulanıyor: `test_writes_use_a_single_statement`in zaten kullandığı `db.statements`
    deseniyle."""
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

    assert "ORDER BY entity_key, observed_at DESC" in _latest_select(db)


def test_latest_observations_is_scoped_to_source_and_entity_kind() -> None:
    """`source_id`/`entity_kind` filtresi düşerse başka kaynağın ya da başka varlık
    türünün gözlemi sessizce karışır — bu test tam o karışmayı yakalar.

    Review #6, ÖLÇÜLDÜ: taklit `params`e göre filtreliyor, SQL METNİNDE `WHERE` var mı
    diye bakmıyor — yani `observations.py`deki WHERE cümlesi düşürülse bile yalnız
    aşağıdaki davranış-temelli iddialar YEŞİL kalırdı. Sorgu metni de AYRICA doğrulanıyor.
    """
    db = FakeObservationDb()
    write_observations(db, (obs("gs", 1.5),))
    write_observations(db, (Observation("understat", "team", "gs", NOW, {"xg": 9.9}),))
    write_observations(db, (Observation("footystats", "player", "gs", NOW, {"xg": 9.9}),))

    result = latest_observations(db, "footystats", "team")

    assert len(result) == 1
    assert result[0].payload["xg"] == 1.5

    assert "WHERE source_id = %s AND entity_kind = %s" in _latest_select(db)
