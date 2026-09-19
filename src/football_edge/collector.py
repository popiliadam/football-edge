from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import httpx
from protego import Protego

from football_edge.sources import Source, guard_path

LOGGER = logging.getLogger("football_edge.collector")


class ContractViolation(RuntimeError):
    """Veri sözleşmesi bozuldu: tazelik, şema ya da içerik türü.

    Yutulursa kaynak arızası SESSİZ olur — spec §8'in panzehiri tam olarak bunun
    gürültülü olmasıdır. Kırılan bir ayrıştırıcı boş liste üretir ve boş liste,
    iddiasız bir turda başarıdan ayırt edilemez.
    """


@dataclass(frozen=True)
class Observation:
    source_id: str
    entity_kind: str
    entity_key: str
    observed_at: datetime
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        """İçeriğin kanonik özeti; aynı gözlem iki kez yazılmasın diye.

        `observed_at` HARİÇTİR: aynı xG tablosunu iki saat arayla görmek yeni bir olgu
        değildir. Zaman dâhil edilseydi depo her turda büyür ve tazelik iddiası
        kendi ürettiği gürültüyle her zaman yeşil olurdu.
        """
        canonical = json.dumps(
            {"k": self.entity_kind, "e": self.entity_key, "p": self.payload},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(f"{self.source_id}{canonical}".encode()).hexdigest()


@dataclass(frozen=True)
class Breaker:
    failures: int
    opened_at: datetime | None


def record(
    breaker: Breaker, now: datetime, *, ok: bool, threshold: int, cooldown: timedelta
) -> Breaker:
    if ok:
        return Breaker(failures=0, opened_at=None)
    failures = breaker.failures + 1
    return Breaker(failures=failures, opened_at=now if failures >= threshold else breaker.opened_at)


def is_open(breaker: Breaker, now: datetime, *, cooldown: timedelta) -> bool:
    if breaker.opened_at is None:
        return False
    return now - breaker.opened_at < cooldown


def fetch_text(
    client: httpx.Client,
    source: Source,
    path: str,
    parser: Protego,
    *,
    expect: str,
    encoding: str | None = None,
    timeout: float = 30.0,
) -> str:
    """İzin → istek → içerik doğrulaması. Bu SIRA yük taşır.

    İzin kontrolü İLK iştir: yanıtı aldıktan sonra filtrelemek, isteği zaten atmış olmak
    demektir ve spec §3.2 "taranmaz" diyor, "okunmaz" değil.

    `expect` zorunludur çünkü bazı uçlar 200 dönüp yanlış içerik verir (spec §7): 200,
    doğru veriyi aldığımızın kanıtı değildir.

    `encoding` verilirse httpx'in tahmini EZİLİR. TFF'de charset yalnız HTTP başlığındadır
    ve gövdede meta yoktur; tahmine bırakılırsa Türkçe karakterler sessizce bozulur ve
    takım adları hiçbir eşleşmeye uymaz.

    `parser: Protego` — stdlib `RobotFileParser` DEĞİL. Task 3 (R10) ayrıştırıcıyı
    `protego`ya çevirdi (joker karakter + RFC 9309 en-uzun-eşleşme desteği için);
    `football_edge.sources.robots_for()` da `Protego` döner. `guard_path` zaten bu tipi
    bekliyor — burada stdlib tipini yazmak `mypy --strict`i düşürürdü.

    `crawl_delay_seconds` BURADA gerçek zaman geçirir (Task 3 yalnız kaydediyordu, hiç
    okumuyordu). FootyStats için 5.0 sn — altı lig sayfası bir turda ~30 sn bekler; bu
    kasıtlıdır, "yavaş" diye optimize edilmez (bkz. config/sources.yaml notu).
    """
    guard_path(parser, source, path)
    if source.crawl_delay_seconds > 0:
        time.sleep(source.crawl_delay_seconds)
    response = client.get(
        f"{source.base_url}{path}",
        headers={"user-agent": source.user_agent},
        timeout=timeout,
        follow_redirects=True,
    )
    response.raise_for_status()
    received = response.headers.get("content-type", "")
    if expect not in received:
        raise ContractViolation(
            f"{source.id}: beklenen content-type '{expect}', gelen '{received}' ({path})"
        )
    if encoding is None:
        return response.text
    return response.content.decode(encoding, errors="strict")


def assert_schema(
    observations: tuple[Observation, ...],
    *,
    source_id: str,
    required: frozenset[str],
    minimum_rows: int,
) -> None:
    if len(observations) < minimum_rows:
        raise ContractViolation(
            f"{source_id}: şema iddiası — en az {minimum_rows} satır beklendi, "
            f"{len(observations)} geldi"
        )
    for entry in observations:
        missing = required - frozenset(entry.payload)
        if missing:
            raise ContractViolation(
                f"{source_id}: şema iddiası — eksik alan {sorted(missing)} ({entry.entity_key})"
            )


def assert_fresh(
    observations: tuple[Observation, ...],
    now: datetime,
    *,
    max_age: timedelta,
    source_id: str,
) -> None:
    if not observations:
        raise ContractViolation(f"{source_id}: tazelik iddiası — hiç gözlem yok")
    newest = max(entry.observed_at for entry in observations)
    if now - newest > max_age:
        raise ContractViolation(
            f"{source_id}: tazelik iddiası — en yeni gözlem {newest.isoformat()}, sınır {max_age}"
        )
