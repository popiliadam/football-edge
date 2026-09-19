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

from football_edge.sources import load_sources, robots_snapshot

SOURCES = Path("config/sources.yaml")
ROBOTS = Path("config/robots")


def live_robots(client: httpx.Client, base_url: str, user_agent: str) -> str:
    """Canlı robots.txt gövdesi. 404 = politika dosyası YOK ve bu BOŞ metne denktir.

    Eksik dosya ile boş dosya farklıdır (bkz. `sources.robots_for`): biri "bilmiyoruz",
    diğeri "kısıt yok". Burada 404, kayıtlı boş anlık görüntüyle eşleşmelidir.
    """
    response = client.get(
        f"{base_url}/robots.txt",
        headers={"user-agent": user_agent},
        timeout=25.0,
        follow_redirects=True,
    )
    return response.text if response.status_code == 200 else ""


def _normalised_newlines(text: str) -> str:
    """`\\r\\n`/`\\r`'yi `\\n`'e indirger — YALNIZ satır sonu STİLİNİ karşılaştırmadan çıkarır.

    `Path.read_text()` bunu OKURKEN sessizce yapar (evrensel satır sonu); `httpx.Response.text`
    YAPMAZ. Normalize etmeden `recorded == current` karşılaştırmak, gövdesi değişmeyen ama
    CRLF döndüren her sunucuda YANLIŞ SAPMA ALARMI üretir (ölçüldü: understat.com robots.txt'i
    CRLF döndürüyor — bkz. Task 3 raporu). Yanlış alarm kaçırılan bulgu kadar zararlıdır: her
    gün kırmızı veren bir iş, gerçek bir sapmayı gürültüye gömer.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")


def main() -> int:
    drifted = 0
    with httpx.Client() as client:
        for source in load_sources(SOURCES):
            snapshot = robots_snapshot(source, ROBOTS)
            if not snapshot.is_file():
                continue
            recorded = _normalised_newlines(snapshot.read_text(encoding="utf-8"))
            try:
                current = _normalised_newlines(
                    live_robots(client, source.base_url, source.user_agent)
                )
            except httpx.HTTPError as error:
                # ÖLÇÜLEMEYEN kaynak geçmek değildir: adıyla yazılır ve iş kırmızı verir.
                sys.stdout.write(f"ÖLÇÜLEMEDİ: {source.id} — {error}\n")
                drifted = 1
                continue
            if current.strip() == recorded.strip():
                sys.stdout.write(f"sapma yok: {source.id}\n")
                continue
            drifted = 1
            sys.stdout.write(f"ROBOTS SAPMASI: {source.id}\n")
            sys.stdout.writelines(
                difflib.unified_diff(
                    recorded.splitlines(keepends=True),
                    current.splitlines(keepends=True),
                    fromfile=f"{source.id} (kayıtlı)",
                    tofile=f"{source.id} (canlı)",
                )
            )
    return drifted


if __name__ == "__main__":
    raise SystemExit(main())
