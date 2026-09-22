#!/usr/bin/env python3
"""Canlı robots.txt'leri commit'lenmiş anlık görüntülerle karşılaştırır.

KAPALI kaynaklar da taranır: kapanan kaynak kadar AÇILAN kaynak da olaydır. Understat
bir gün robots'unu gevşetirse bunu görmek isteriz; görmek, kararı değiştirmek zorunda
değildir ama kararın dayanağını tazeler.

`--refresh`: canlısı anlık görüntüyle aynı ölçülen ("sapma yok") kaynağın `robots_verified_at`i
7 günden eskiyse `config/sources.yaml`da bugüne çekilir — aynı kalan robots.txt bir yeniden
doğrulamadır. Sapan ya da ölçülemeyen kaynağın tarihine dokunulmaz; tur yine kırmızı verir.
"""

from __future__ import annotations

import argparse
import difflib
import sys
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import yaml

from football_edge.sources import Source, load_sources, robots_snapshot, snapshot_from_status

SOURCES = Path("config/sources.yaml")
ROBOTS = Path("config/robots")
# Her gün değil: tazeleme bir bot commit'idir. Kapının 30 günlük penceresinde 23 günlük
# arıza payı kalır.
REFRESH_AFTER = timedelta(days=7)


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


def _child(node: yaml.Node | None, key: str) -> yaml.Node:
    """Eşlemede `key`in TEK değer düğümü; yoksa ya da birden çoksa hata — hangisi olduğu
    tahmin edilmez (PyYAML yinelenen anahtarda sessizce sonuncuyu alır)."""
    pairs = node.value if isinstance(node, yaml.MappingNode) else []
    values: list[yaml.Node] = [value for name, value in pairs if name.value == key]
    if len(values) != 1:
        raise ValueError(f"{SOURCES}: '{key}' {len(values)} kez bulundu, tek bekleniyordu")
    return values[0]


def _verified_span(text: str, source_id: str) -> tuple[int, int]:
    """`source_id` kaydının `robots_verified_at` DEĞERİNİN metindeki [başlangıç, bitiş) aralığı.

    Yer satır aramasıyla değil YAML düğüm konumuyla bulunur: `load_sources`in okuduğu değerin
    kendisidir — aynı tarihi taşıyan bir yorum ya da katlanmış not satırı değil.
    """
    entries: list[yaml.Node] = _child(yaml.compose(text, Loader=yaml.SafeLoader), "sources").value
    matches = [entry for entry in entries if _child(entry, "id").value == source_id]
    if len(matches) != 1:
        raise ValueError(f"{SOURCES}: '- id: {source_id}' kaydı {len(matches)} kez bulundu")
    node = _child(matches[0], "robots_verified_at")
    return node.start_mark.index, node.end_mark.index


def _bump(text: str, source: Source, today: date) -> str:
    """Yalnız o kaynağın tarih değerinin karakterlerini değiştirir; metnin kalanı aynen kalır."""
    start, end = _verified_span(text, source.id)
    if text[start:end] != source.robots_verified_at.isoformat():
        raise ValueError(
            f"{SOURCES}: {source.id} robots_verified_at beklenen biçimde değil "
            f"({text[start:end]!r}) — tarih yazılmadı"
        )
    return f"{text[:start]}{today.isoformat()}{text[end:]}"


def refresh(path: Path, verified: Sequence[Source], today: date) -> str:
    """`verified` kaynaklardan tarihi `REFRESH_AFTER`dan eski olanları bugüne çeker.

    Dosya yeniden YAZDIRILMAZ (yaml.dump yorumları ve katlanmış notları siler); hedefli değer
    düzenlemesidir. Konum bulunamazsa hiçbir şey yazılmaz ve hata yükselir: sessizce atlanan
    bir tarih 30 gün sonra kapıyı kırmızıya düşürürdü.
    """
    due = [source for source in verified if today - source.robots_verified_at > REFRESH_AFTER]
    if not due:
        return "tazeleme: 7 günden eski doğrulanmış tarih yok\n"
    # Ham bayt: `read_text` satır sonlarını çevirir, dosyanın kalanı bayt bayt korunmalı.
    text = path.read_bytes().decode("utf-8")
    for source in due:
        text = _bump(text, source, today)
    path.write_bytes(text.encode("utf-8"))
    return "".join(
        f"yeniden doğrulandı: {source.id} {source.robots_verified_at} → {today}\n" for source in due
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="canlı robots.txt ↔ anlık görüntü sapması")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="canlısı aynı kalan kaynağın 7 günden eski robots_verified_at'ini bugüne çek",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    transport: httpx.BaseTransport | None = None,
    today: date | None = None,
) -> int:
    args = _parser().parse_args(argv)
    drifted = False
    verified: tuple[Source, ...] = ()
    with httpx.Client(transport=transport) as client:
        for source in load_sources(SOURCES):
            snapshot = robots_snapshot(source, ROBOTS)
            if not snapshot.is_file():
                continue
            recorded = _normalised_newlines(snapshot.read_text(encoding="utf-8"))
            line, failed = _report_one(client, source, recorded)
            sys.stdout.write(line)
            drifted = drifted or failed
            verified = verified if failed else (*verified, source)
    if args.refresh:
        # Kapı (`collect sources-audit`) UTC gününü kullanır: yerel gün ondan ileride olabilir
        # ve yazılan tarih kapıda "gelecekte" ihlali olurdu.
        sys.stdout.write(refresh(SOURCES, verified, today or datetime.now(UTC).date()))
    return 1 if drifted else 0


if __name__ == "__main__":
    raise SystemExit(main())
