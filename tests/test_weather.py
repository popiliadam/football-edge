from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from football_edge.collector import ContractViolation
from football_edge.collectors.weather import parse_forecast

FIXTURE = Path("tests/fixtures/venue/open-meteo.json")


def payload() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.contract
def test_picks_the_hour_nearest_to_kickoff() -> None:
    body = payload()
    first_hour = str(body["hourly"]["time"][0])  # type: ignore[index]
    kickoff = datetime.fromisoformat(first_hour).replace(tzinfo=UTC)
    values = parse_forecast(body, kickoff)
    assert values["temperature_c"] == float(body["hourly"]["temperature_2m"][0])  # type: ignore[index]


@pytest.mark.contract
def test_elevation_comes_straight_from_the_response() -> None:
    """Rakım için ayrı kaynak yok: Open-Meteo zaten veriyor."""
    values = parse_forecast(payload(), datetime(2026, 9, 19, 0, 0, tzinfo=UTC))
    assert values["elevation_m"] == float(payload()["elevation"])  # type: ignore[index]


def test_kickoff_outside_the_forecast_window_raises() -> None:
    """Tahmin penceresi dışındaki saat için EN YAKIN saati vermek sessiz yanlış veridir."""
    with pytest.raises(ContractViolation, match="pencere"):
        parse_forecast(payload(), datetime(2030, 1, 1, 12, 0, tzinfo=UTC))
