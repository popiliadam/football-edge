from __future__ import annotations

import json
from typing import Any

import psycopg

from football_edge.collector import Observation
from football_edge.ledger import canonical_timestamp

_OBS_COLUMNS: tuple[tuple[str, str], ...] = (
    ("source_id", "text"),
    ("entity_kind", "text"),
    ("entity_key", "text"),
    ("observed_at", "timestamptz"),
    ("payload", "jsonb"),
    ("content_hash", "text"),
)

_OBS_NAMES = ", ".join(name for name, _ in _OBS_COLUMNS)
_OBS_ARRAYS = ", ".join(f"%({name})s::{kind}[]" for name, kind in _OBS_COLUMNS)

# Task 1'deki oran yazımıyla AYNI desen: tek ifade, kolon dizileri, RETURNING.
# `ON CONFLICT DO NOTHING` idempotentliği verir — aynı xG tablosu her turda yeniden
# gözlenir ve ikinci kez yazılmaz.
INSERT_OBSERVATIONS = f"""
    INSERT INTO source_observations ({_OBS_NAMES})
    SELECT {_OBS_NAMES}
    FROM unnest({_OBS_ARRAYS}) AS t({_OBS_NAMES})
    ON CONFLICT (source_id, entity_kind, entity_key, content_hash) DO NOTHING
    RETURNING entity_key
"""

# `obs_lookup_idx (source_id, entity_kind, entity_key, observed_at desc)` bu sorguyu
# doğrudan karşılar: DISTINCT ON entity_key başına yalnız en yeni satırı tutar.
SELECT_LATEST_OBSERVATIONS = """
    SELECT DISTINCT ON (entity_key) source_id, entity_kind, entity_key, observed_at, payload
    FROM source_observations
    WHERE source_id = %s AND entity_kind = %s
    ORDER BY entity_key, observed_at DESC
"""


def write_observations(conn: psycopg.Connection[Any], observations: tuple[Observation, ...]) -> int:
    """YENİ yazılan gözlem sayısını döner (yinelenenler sayılmaz)."""
    if not observations:
        return 0
    columns: dict[str, list[Any]] = {
        "source_id": [entry.source_id for entry in observations],
        "entity_kind": [entry.entity_kind for entry in observations],
        "entity_key": [entry.entity_key for entry in observations],
        "observed_at": [canonical_timestamp(entry.observed_at) for entry in observations],
        "payload": [
            json.dumps(entry.payload, sort_keys=True, ensure_ascii=False) for entry in observations
        ],
        "content_hash": [entry.content_hash for entry in observations],
    }
    with conn.cursor() as cur:
        cur.execute(INSERT_OBSERVATIONS, columns)
        return len(cur.fetchall())


def latest_observations(
    conn: psycopg.Connection[Any], source_id: str, entity_kind: str
) -> tuple[Observation, ...]:
    """Kaynak + varlık türü başına HER `entity_key` için EN YENİ gözlemi döner.

    Yazma tarafı `ON CONFLICT DO NOTHING` ile idempotent olduğu için aynı takımın birden
    çok gözlemi depoda birikir (her biri farklı `content_hash`/`observed_at`); okuyan taraf
    ham geçmişi değil GÜNCEL DURUMU ister. `entity_key` başına en yeniyi seçmeden dönmek,
    aynı takımın eski ve yeni değerini aynı anda görünür kılar ve çağıranı hangisinin
    güncel olduğuna kendi tahmin etmeye zorlar.

    `content_hash` dönüşte SAKLANMAZ, `Observation.content_hash` özelliği üzerinden
    YENİDEN HESAPLANIR. Bu güvenlidir: hash zaten `observed_at`i dışarıda bırakıyor
    (bkz. `Observation.content_hash` docstring'i), yani entity_kind/entity_key/payload/
    source_id'den yeniden hesaplamak yazma anındaki değerle birebir eşleşir.
    """
    with conn.cursor() as cur:
        cur.execute(SELECT_LATEST_OBSERVATIONS, (source_id, entity_kind))
        rows = cur.fetchall()
    return tuple(
        Observation(
            source_id=str(row[0]),
            entity_kind=str(row[1]),
            entity_key=str(row[2]),
            observed_at=row[3],
            payload=dict(row[4]),
        )
        for row in rows
    )
