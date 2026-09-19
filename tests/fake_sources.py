"""Testler için kaynak kaydı kurgusu."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from football_edge.sources import Source


def fake_source(**overrides: object) -> Source:
    # `access_basis`/`terms_url`: Task 3'te `Source`e eklendi (R8 — robots/api_terms ayrımı).
    # Brief'in bu yardımcı için verdiği anlık görüntü bu iki alanı taşımıyordu; eklenmezse
    # `Source(**{...})` eksik pozisyonel argümanla patlar. Varsayılanlar `tests/test_sources.py`
    # ile aynı: robots-tabanlı, gerekçesiz terms_url gerektirmeyen sıradan kaynak.
    base = {
        "id": "footystats",
        "base_url": "https://example.test",
        "user_agent": "football-edge-test/0.1",
        "crawl_delay_seconds": 0.0,
        "robots_verified_at": date(2026, 9, 19),
        "declared_paths": (),
        "enabled": True,
        "note": "",
        "access_basis": "robots",
        "terms_url": "",
    }
    return Source(**{**base, **overrides})  # type: ignore[arg-type]


def write_robots(directory: Path, source_id: str, body: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{source_id}.txt"
    target.write_text(body, encoding="utf-8")
    return target
