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

from football_edge.sources import Source, SourceBlocked, guard_path

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
    breaker: Breaker, now: datetime, *, ok: bool, threshold: int = 3, cooldown: timedelta
) -> Breaker:
    if ok:
        return Breaker(failures=0, opened_at=None)
    failures = breaker.failures + 1
    return Breaker(failures=failures, opened_at=now if failures >= threshold else breaker.opened_at)


def is_open(breaker: Breaker, now: datetime, *, cooldown: timedelta) -> bool:
    if breaker.opened_at is None:
        return False
    return now - breaker.opened_at < cooldown


# Bir yönlendirme zincirinin makul üst sınırı. httpx'in kendi varsayılanı (20) çoğu
# meşru senaryo için gereğinden büyük; burada amaç sonsuz döngüyü kesmek, cömert olmak
# değil — beş kaynağın hiçbiri normalde birden fazla sıçrama yapmıyor.
_MAX_REDIRECTS = 5


def _guarded_get(
    client: httpx.Client,
    source: Source,
    path: str,
    parser: Protego,
    *,
    timeout: float,
) -> httpx.Response:
    """İzinli her SIÇRAMAYI (redirect) AYRI AYRI doğrular; sıçramayı httpx'e bırakmaz.

    `follow_redirects=True` `guard_path`i tamamen atlatıyordu (review #8): robots yalnız
    İLK URL'e soruluyordu, 3xx'in `Location`'ı — ÇAPRAZ-HOST dahil — hiç sorulmadan
    istendi. Bağlayıcı kural "hiçbir istek atılmadan önce guard_path"tı (spec §3.2); bir
    yönlendirme zinciri tam olarak böyle isteklerdir, kimsenin kontrol etmediği yol ve
    host'lara. `test_fetch_refuses_a_disallowed_path` yalnız İLK sıçramayı kanıtlıyordu.

    Her turda: (1) mevcut `path`i guard_path'ten geçir, (2) `follow_redirects=False` ile
    iste, (3) 3xx değilse dön, (4) 3xx ise `Location`'ı ÇÖZ ve kaynağın `base_url`
    ORİJİNİYLE (scheme+host+port) karşılaştır — ÇIPLAK METİN ÖNEKİ değil: `"https://
    footystats.org.evil.com"` `"https://footystats.org"` ile BAŞLAR ama farklı bir
    host'tur, bu yüzden `.host` alanları AYRI AYRI karşılaştırılır. Orijin farklıysa
    `SourceBlocked` — o host'un robots'u hiç sorulmadı, sormaya da yetkimiz yok.
    """
    base = httpx.URL(source.base_url)
    for _ in range(_MAX_REDIRECTS):
        guard_path(parser, source, path)
        if source.crawl_delay_seconds > 0:
            time.sleep(source.crawl_delay_seconds)
        response = client.get(
            f"{source.base_url}{path}",
            headers={"user-agent": source.user_agent},
            timeout=timeout,
            follow_redirects=False,
        )
        if not response.is_redirect:
            response.raise_for_status()
            return response
        target = response.headers.get("location", "")
        resolved = response.url.join(target)
        if (resolved.scheme, resolved.host, resolved.port) != (base.scheme, base.host, base.port):
            raise SourceBlocked(
                f"{source.id}: yönlendirme base_url orijini dışına çıkıyor — {resolved}"
            )
        path = str(resolved)[len(source.base_url) :]
    raise ContractViolation(f"{source.id}: {_MAX_REDIRECTS} yönlendirmeden sonra hâlâ sıçrıyor")


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
    demektir ve spec §3.2 "taranmaz" diyor, "okunmaz" değil. Bu yalnız İLK isteğe değil,
    yönlendirmenin HER sıçramasına da uygulanır — bkz. `_guarded_get`.

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
    response = _guarded_get(client, source, path, parser, timeout=timeout)
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
    """Beklenen alanlar VAR MI değil, makul bir DEĞER TAŞIYOR MU diye bakar (review #4).

    Yalnız anahtarın varlığına bakan bir kontrol `{"xg": None}` ya da `{"xg": ""}`den
    geçer — bir markup değişikliğinden sonra hâlâ eşleşen ama artık hiçbir şey taşımayan
    bir seçiciyle BİREBİR AYNI arıza şeklidir, ve boş-liste kadar (belki daha) yaygındır.
    Bu yüzden `None` ve `""` "alan yok" sayılır; `missing` bunlara göre hesaplanır.
    """
    if len(observations) < minimum_rows:
        raise ContractViolation(
            f"{source_id}: şema iddiası — en az {minimum_rows} satır beklendi, "
            f"{len(observations)} geldi"
        )
    for entry in observations:
        present = frozenset(
            key for key, value in entry.payload.items() if value is not None and value != ""
        )
        missing = required - present
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
    """`observed_at` KAYNAKTAN gelmiş olmalı — bir feed'in `pubDate`'i, bir fikstürün ilan
    edilen tarihi. Bu iddia YALNIZ o durumda anlamlıdır; iki durumda YANLIŞ GÜVEN verir
    (R23 — bkz. Task 4 review #9):

    1. **Bir toplayıcının kendi damgaladığı `now()` üzerinde ÇAĞRILMAMALI.** Bir toplayıcı
       `Observation(..., observed_at=now)` üretip o partiyi HEMEN `assert_fresh(..., now)`a
       sokarsa, `now - now ≈ 0 ≤ max_age` HER ZAMAN doğrudur — KIRILAMAYAN bir iddiadır.
       Kırılamayan bir test testsizlikten kötüdür (bu projenin kendi kuralı); bu fonksiyon
       için de geçerli. Anlamlı tazelik kontrolü yalnız zaman damgası KAYNAĞA aitse vardır.
    2. **`latest_observations(...)` çıktısı üzerinde YANILTICI.** `content_hash`
       `observed_at`i DIŞLADIĞI (bkz. `Observation.content_hash`) ve depo benzersizlik
       anahtarı `content_hash`i İÇERDİĞİ için, değişmeyen bir içeriğin yeniden gözlenmesi
       `ON CONFLICT DO NOTHING` ile no-op'tur — saklanan `observed_at` İLK görülme anını
       taşımaya devam eder. Bir takımın xG'si 10 gündür DEĞİŞMEDEN kalırsa
       `assert_fresh(latest_observations(...), max_age=7g)` kaynağı BUGÜN başarıyla okumuş
       olsanız bile "bayat" der — bu bir kaynak arızası değil, deponun idempotentliğinin
       yan etkisidir.

    **Gerçek kaynak-tazeliği** (N tur boyunca `content_hash` hiç değişmiyor mu) bu
    fonksiyonun işi DEĞİL — ertelendi, faz handoff'unda kapının ÖLÇMEDİĞİ olarak
    adlandırılacak.

    Ayrıca `now`dan GELECEKTE bir `observed_at`i de reddeder (R13'teki `sources.
    _date_violation` ile aynı arıza sınıfı, aynı fonksiyona sessizce döndü): `now - newest`
    negatifken eski kod hiç raise ETMİYORDU, yani 400 gün ileri tarihli tek bir satır
    tüm partiyi SÜRESİZ taze gösterebiliyordu.
    """
    if not observations:
        raise ContractViolation(f"{source_id}: tazelik iddiası — hiç gözlem yok")
    newest = max(entry.observed_at for entry in observations)
    age = now - newest
    if age < timedelta(0):
        raise ContractViolation(
            f"{source_id}: tazelik iddiası — en yeni gözlem GELECEKTE {newest.isoformat()} "
            f"(şimdi {now.isoformat()}) — bir hatıra gözlem olamaz"
        )
    if age > max_age:
        raise ContractViolation(
            f"{source_id}: tazelik iddiası — en yeni gözlem {newest.isoformat()}, sınır {max_age}"
        )
