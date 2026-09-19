#!/usr/bin/env python3
"""Canlı robots.txt'leri commit'lenmiş anlık görüntülerle karşılaştırır.

KAPALI kaynaklar da taranır: kapanan kaynak kadar AÇILAN kaynak da olaydır. Understat
bir gün robots'unu gevşetirse bunu görmek isteriz; görmek, kararı değiştirmek zorunda
değildir ama kararın dayanağını tazeler.
"""

from __future__ import annotations

import difflib
import sys
from pathlib import Path

import httpx

from football_edge.sources import Source, load_sources, robots_snapshot, snapshot_from_status

SOURCES = Path("config/sources.yaml")
ROBOTS = Path("config/robots")


def live_robots(client: httpx.Client, base_url: str, user_agent: str) -> httpx.Response:
    """Canlı robots.txt için HAM HTTP yanıtı.

    Durum kodunun NE ANLAMA geldiği (politika var / politika yok / ölçülemedi) burada
    KARAR VERİLMEZ — bu, `sources.snapshot_from_status`'ın işi (review R15: "bu HTTP
    durumu bir robots anlık görüntüsü için ne anlama gelir" kaynak-politikası mantığıdır,
    betik iskeleti değil, `tests/test_sources.py`'de sıradan test edilir). Bu fonksiyon
    yalnız ağa çıkar.
    """
    return client.get(
        f"{base_url}/robots.txt",
        headers={"user-agent": user_agent},
        timeout=25.0,
        follow_redirects=True,
    )


def _normalised_newlines(text: str) -> str:
    """`\\r\\n`/`\\r`'yi `\\n`'e indirger — YALNIZ satır sonu STİLİNİ karşılaştırmadan çıkarır.

    `Path.read_text()` bunu OKURKEN sessizce yapar (evrensel satır sonu); `httpx.Response.text`
    YAPMAZ. Normalize etmeden `recorded == current` karşılaştırmak, gövdesi değişmeyen ama
    CRLF döndüren her sunucuda YANLIŞ SAPMA ALARMI üretir (ölçüldü: understat.com robots.txt'i
    CRLF döndürüyor — bkz. Task 3 raporu). Yanlış alarm kaçırılan bulgu kadar zararlıdır: her
    gün kırmızı veren bir iş, gerçek bir sapmayı gürültüye gömer.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _report_one(client: httpx.Client, source: Source, recorded: str) -> tuple[str, bool]:
    """Tek kaynağı ölçer; (stdout'a yazılacak metin, turu kırmızı yapsın mı) döner."""
    try:
        response = live_robots(client, source.base_url, source.user_agent)
    except httpx.HTTPError as error:
        # ÖLÇÜLEMEYEN kaynak geçmek değildir: adıyla yazılır ve iş kırmızı verir.
        return f"ÖLÇÜLEMEDİ: {source.id} — {error}\n", True
    live_body = snapshot_from_status(response.status_code, response.text)
    if live_body is None:
        # `snapshot_from_status` 404/410 dışındaki her non-200'ü None döner — taşıma
        # hatasıyla (yukarıdaki except) AYNI muameleyi görür: ikisi de "bu turda
        # ölçemedik", ikisi de geçmek değil.
        return f"ÖLÇÜLEMEDİ: {source.id} — HTTP {response.status_code}\n", True
    current = _normalised_newlines(live_body)
    if current.strip() == recorded.strip():
        return f"sapma yok: {source.id}\n", False
    diff = "".join(
        difflib.unified_diff(
            recorded.splitlines(keepends=True),
            current.splitlines(keepends=True),
            fromfile=f"{source.id} (kayıtlı)",
            tofile=f"{source.id} (canlı)",
        )
    )
    return f"ROBOTS SAPMASI: {source.id}\n{diff}", True


def main() -> int:
    drifted = False
    with httpx.Client() as client:
        for source in load_sources(SOURCES):
            snapshot = robots_snapshot(source, ROBOTS)
            if not snapshot.is_file():
                continue
            recorded = _normalised_newlines(snapshot.read_text(encoding="utf-8"))
            line, failed = _report_one(client, source, recorded)
            sys.stdout.write(line)
            drifted = drifted or failed
    return 1 if drifted else 0


if __name__ == "__main__":
    raise SystemExit(main())
