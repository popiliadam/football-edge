from __future__ import annotations

from datetime import datetime
from typing import Any

from football_edge.collector import ContractViolation, Observation

SOURCE_ID = "wikidata"
ENTITY_PATH = "/wiki/Special:EntityData/{qid}.json"


def parse_entity_coordinates(payload: dict[str, Any], qid: str) -> tuple[float, float]:
    """P625 (koordinat konumu) talebinden (enlem, boylam).

    SPARQL DEĞİL REST: `Special:EntityData/<QID>.json` düz bir GET'tir. SPARQL ucu yerel
    `outward_action_gate` tarafından `net_post` olarak engelleniyor (ölçüldü 2026-09-19) ve
    tek bir varlık için zaten gereksiz.
    """
    claims = payload.get("entities", {}).get(qid, {}).get("claims", {})
    statements = claims.get("P625")
    if not statements:
        raise ContractViolation(f"{SOURCE_ID}: {qid} için P625 (koordinat) yok")
    value = statements[0]["mainsnak"]["datavalue"]["value"]
    # Alanlar ADLA okunur: konumla okumak enlem/boylamı takas eder ve hava tahmini
    # başka bir kıtadan gelir — hata vermeden.
    return float(value["latitude"]), float(value["longitude"])


def venue_observation(
    qid: str, latitude: float, longitude: float, *, observed_at: datetime
) -> Observation:
    return Observation(
        source_id=SOURCE_ID,
        entity_kind="venue",
        entity_key=qid,
        observed_at=observed_at,
        payload={"latitude": latitude, "longitude": longitude},
    )
