"""Haber gözlemi → `news_items` (spec §4; R166, R172): `available_at`i veritabanı saati kurar."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from football_edge.collector import ContractViolation
from football_edge.features import __main__ as cli
from football_edge.features.news import (
    INSERT_NEWS,
    SYNC_LOOKBACK,
    NewsDraft,
    archive_available_at,
    load_news,
    news_from_observations,
    news_hash,
    sync_news,
    write_news,
)
from football_edge.features.types import ARCHIVE_CLAIMED, OBSERVED, StoredNews
from tests.fake_news_db import FakeNewsDb

T0 = datetime(2026, 9, 20, 9, 30, tzinfo=UTC)
TICK = timedelta(microseconds=1)
URL = "https://ajansspor.com/haber/galatasaray-sakatlik-1"
TITLE = "Galatasaray'da sakatlık"


def _payload(title: str = TITLE, url: str = URL, published: datetime = T0) -> dict[str, Any]:
    return {"title": title, "url": url, "published_at": published.isoformat(), "source_id": "x"}


def _row(observed_at: datetime = T0, **payload: Any) -> dict[str, Any]:
    return {"source_id": "ajansspor", "observed_at": observed_at, "payload": _payload(**payload)}


@pytest.mark.leakage
def test_a_live_draft_carries_the_publisher_claim_and_no_availability() -> None:
    """`observed_at` yayıncının iddiasıdır (R172): kullanılabilirlik anı ondan KURULMAZ."""
    (draft,) = news_from_observations([_row()])

    assert draft.published_at_claimed == T0
    assert draft.available_at is None
    assert draft.availability_basis == OBSERVED
    assert (draft.lang, draft.title, draft.url, draft.body) == ("tr", TITLE, URL, None)
    assert draft.content_hash == news_hash("ajansspor", URL, TITLE, None)


@pytest.mark.leakage
def test_reobserved_content_keeps_the_earliest_claim() -> None:
    later = T0 + timedelta(hours=5)

    (draft,) = news_from_observations([_row(later, published=later), _row(T0, published=T0)])

    assert draft.published_at_claimed == T0


def test_a_changed_title_is_a_new_item() -> None:
    drafts = news_from_observations([_row(), _row(T0 + timedelta(hours=1), title="Yeni başlık")])

    assert [draft.title for draft in drafts] == [TITLE, "Yeni başlık"]


@pytest.mark.parametrize("missing", ["title", "url"])
def test_a_payload_without_title_or_url_is_a_contract_violation(missing: str) -> None:
    row = _row()
    payload = {key: value for key, value in row["payload"].items() if key != missing}

    with pytest.raises(ContractViolation, match=missing):
        news_from_observations([{**row, "payload": payload}])


@pytest.mark.leakage
def test_a_naive_observed_at_is_a_contract_violation() -> None:
    with pytest.raises(ContractViolation, match="observed_at"):
        news_from_observations([_row(T0.replace(tzinfo=None))])


def test_a_source_without_a_language_is_a_contract_violation() -> None:
    with pytest.raises(ContractViolation, match="googlenews"):
        news_from_observations([{**_row(), "source_id": "googlenews"}])


@pytest.mark.leakage
def test_stored_news_refuses_naive_times() -> None:
    naive = T0.replace(tzinfo=None)

    with pytest.raises(ValueError, match="available_at saat dilimsiz"):
        StoredNews(None, "s", "tr", "t", None, "u", None, naive, OBSERVED, "h")
    with pytest.raises(ValueError, match="first_seen_at saat dilimsiz"):
        StoredNews(None, "s", "tr", "t", None, "u", None, T0, OBSERVED, "h", naive)


def test_stored_news_refuses_an_unknown_basis() -> None:
    with pytest.raises(ValueError, match="availability_basis"):
        StoredNews(None, "s", "tr", "t", None, "u", None, T0, "guessed", "h")


@pytest.mark.leakage
def test_a_live_draft_cannot_bring_its_own_availability() -> None:
    with pytest.raises(ValueError, match="veritabanı kurar"):
        NewsDraft("ajansspor", "tr", "t", None, "u", T0, OBSERVED, "h", available_at=T0)


@pytest.mark.leakage
def test_an_archive_draft_needs_a_claim_and_a_non_negative_lag() -> None:
    ok = NewsDraft("arsiv", "en", "t", None, "u", T0, ARCHIVE_CLAIMED, "h", available_at=T0)

    assert ok.available_at == T0
    with pytest.raises(ValueError, match="iddia"):
        NewsDraft("arsiv", "en", "t", None, "u", None, ARCHIVE_CLAIMED, "h", available_at=T0)
    with pytest.raises(ValueError, match="iddia"):
        NewsDraft("arsiv", "en", "t", None, "u", T0, ARCHIVE_CLAIMED, "h", available_at=T0 - TICK)


@pytest.mark.leakage
def test_archive_news_is_available_after_the_safety_lag() -> None:
    assert archive_available_at(T0, timedelta(hours=6)) == T0 + timedelta(hours=6)


@pytest.mark.leakage
def test_archive_lag_cannot_be_negative_nor_the_time_naive() -> None:
    with pytest.raises(ValueError, match="negatif"):
        archive_available_at(T0, timedelta(hours=-1))
    with pytest.raises(ValueError, match="saat dilimsiz"):
        archive_available_at(T0.replace(tzinfo=None), timedelta(hours=1))


@pytest.mark.leakage
def test_availability_is_computed_by_the_database_clock_at_insert() -> None:
    """Python saati değil `now()`: canlı satırda kısıt `available_at ≥ first_seen_at`i ister."""
    sql = " ".join(INSERT_NEWS.split())

    assert "greatest(now(), published_at_claimed)" in sql
    assert f"WHEN availability_basis = '{OBSERVED}'" in sql
    assert "ON CONFLICT (source_id, content_hash) DO NOTHING" in sql


def test_sync_news_writes_each_item_once() -> None:
    db = FakeNewsDb(now=T0 + timedelta(minutes=30))
    db.observe("ajansspor", T0, _payload())
    db.observe("ajansspor", T0 + timedelta(minutes=10), _payload(title="İkinci haber"))

    assert sync_news(db) == 2  # type: ignore[arg-type]
    assert sync_news(db) == 0  # type: ignore[arg-type]
    assert [row["title"] for row in db.news] == [TITLE, "İkinci haber"]


@pytest.mark.leakage
def test_news_synced_later_is_available_from_the_sync_not_the_claim() -> None:
    synced = T0 + timedelta(days=3)
    db = FakeNewsDb(now=synced)
    db.observe("ajansspor", T0, _payload())

    sync_news(db)  # type: ignore[arg-type]
    (item,) = load_news(db, since=T0)  # type: ignore[arg-type]

    assert item.published_at_claimed == T0
    assert item.available_at == item.first_seen_at == synced


@pytest.mark.leakage
def test_a_later_resync_does_not_move_availability() -> None:
    db = FakeNewsDb(now=T0 + timedelta(hours=1))
    db.observe("ajansspor", T0, _payload())
    sync_news(db)  # type: ignore[arg-type]
    db.now = T0 + timedelta(days=2)
    db.observe("ajansspor", T0 + timedelta(hours=2), _payload(published=T0 + timedelta(hours=2)))

    assert sync_news(db) == 0  # type: ignore[arg-type]
    (item,) = load_news(db, since=T0)  # type: ignore[arg-type]
    assert item.available_at == T0 + timedelta(hours=1)


def test_sync_news_reads_only_news_of_sources_with_a_language() -> None:
    db = FakeNewsDb(now=T0)
    db.observe("ajansspor", T0, _payload())
    db.observe("googlenews", T0, _payload(title="başka kaynak"))
    db.observe("ajansspor", T0, {"team_name": "Galatasaray"}, kind="team")

    assert sync_news(db) == 1  # type: ignore[arg-type]
    assert [row["source_id"] for row in db.news] == ["ajansspor"]


def test_sync_news_since_skips_older_observations() -> None:
    db = FakeNewsDb(now=T0 + timedelta(days=2))
    db.observe("ajansspor", T0, _payload())
    db.observe("ajansspor", T0 + timedelta(days=2), _payload(title="Yeni"))

    assert sync_news(db, since=T0 + timedelta(days=1)) == 1  # type: ignore[arg-type]
    assert [row["title"] for row in db.news] == ["Yeni"]


def test_archive_drafts_keep_their_own_availability() -> None:
    db = FakeNewsDb(now=T0 + timedelta(days=400))
    lagged = archive_available_at(T0, timedelta(hours=6))
    draft = NewsDraft("arsiv", "en", "t", None, "u", T0, ARCHIVE_CLAIMED, "h" * 64, lagged)

    assert write_news(db, [draft]) == 1  # type: ignore[arg-type]
    (item,) = load_news(db, since=T0)  # type: ignore[arg-type]
    assert item.available_at == lagged
    assert item.first_seen_at == T0 + timedelta(days=400)


def test_load_news_returns_stored_items_with_their_ids() -> None:
    db = FakeNewsDb(now=T0)
    db.observe("ajansspor", T0, _payload())
    sync_news(db)  # type: ignore[arg-type]

    (item,) = load_news(db, since=T0)  # type: ignore[arg-type]

    assert item.item_id == 1
    assert load_news(db, since=T0 + TICK) == ()  # type: ignore[arg-type]


def test_sync_news_command_commits_reports_and_looks_back_a_week(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    now = T0 + timedelta(hours=1)
    db = FakeNewsDb(now=now)
    db.observe("ajansspor", T0, _payload())
    db.observe("ajansspor", now - SYNC_LOOKBACK - TICK, _payload(title="Pencere dışı"))
    monkeypatch.setattr(cli, "connect", lambda: db)
    monkeypatch.setattr(cli, "_now", lambda: now)

    with caplog.at_level(logging.INFO):
        code = cli.main(["sync-news"])

    assert code == 0
    assert db.commits == 1
    assert [row["title"] for row in db.news] == [TITLE]
    assert "haber: yeni 1" in caplog.text


def test_sync_news_command_names_a_broken_payload(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    db = FakeNewsDb(now=T0)
    db.observe("ajansspor", T0, {"url": URL})
    monkeypatch.setattr(cli, "connect", lambda: db)
    monkeypatch.setattr(cli, "_now", lambda: T0)

    code = cli.main(["sync-news"])

    assert code == cli.EXIT_SOURCE_FAILED
    assert db.commits == 0
    assert "'title' yok" in caplog.text


# ── Review Focus: kaynağın biçim oynamaları ve ileri tarihli iddia ───────────────────────────


@pytest.mark.leakage
def test_whitespace_only_title_drift_does_not_make_a_second_item() -> None:
    """Sitemap başlığı sonda boşlukla yeniden yayınlanırsa ikinci bir haber doğmamalı."""
    later = T0 + timedelta(hours=3)

    (draft,) = news_from_observations([_row(), _row(later, title=f"  {TITLE} ", published=later)])

    assert draft.published_at_claimed == T0


@pytest.mark.leakage
def test_a_post_dated_claim_is_not_available_before_the_claim() -> None:
    """Yayıncı iddiası bizim saatimizden ilerideyse haber iddiadan önce kullanılamaz."""
    ahead = T0 + timedelta(hours=4)
    db = FakeNewsDb(now=T0)
    db.observe("ajansspor", ahead, _payload(published=ahead))

    sync_news(db)  # type: ignore[arg-type]
    (item,) = load_news(db, since=T0)  # type: ignore[arg-type]

    assert (item.first_seen_at, item.available_at) == (T0, ahead)
