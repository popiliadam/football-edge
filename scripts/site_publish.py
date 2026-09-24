#!/usr/bin/env python3
"""Yayının iki kapısı (spec §11, §6.4/3f, AK20 b): `site.yml` koşar; biri kırmızıysa yayın yok.

`slugs` (yayından ÖNCE): önceki yayının `/data/slugs.json`ı yeni derlemenin
`web/out/data/slugs.json`ıyla karşılaştırılır. Kaybolan her lig slug'ı `config/site_redirects.yaml`
`gone:` listesinde, kaybolan her takım slug'ı `renamed:` eşlemesinde (hedefi yeni derlemede var) ya
da ligi `gone:`da olmalı. Önceki yayın okunamazsa kırmızı; yalnız açık `--first-publish` ile ve
site GERÇEK bir HTTP yanıtıyla önceki yayının olmadığını söylediğinde (200 dışı, ör. 404) geçer.
Site erişilemezse (bağlantı yok, HTTP 0) `--first-publish` da kırmızıdır (spec §11, AK20 b).

`live` (yayından SONRA): canlı `/data/snapshot.sha256` indirilir; hex alanı derlenmiş
`web/out/data/snapshot.sha256` ve dışa aktarımın `web/.snapshot/snapshot.sha256` hex alanıyla eşit
olmalı (yayımlanan = doğrulanan). Örnek sayfaların HEAD başlıkları `web/out/_headers`le aynı
olmalı: sayfanın CSP'si birebir, bayrak kapalıyken `X-Robots-Tag: noindex`.

Taban adres `web/site.config.ts` `SITE_URL`dir (tek kaynak). Ana makine `.invalid` ile bitiyorsa
(yer tutucu, AK4 kararı yok) iki komut da ağa çıkmadan kırmızıdır.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import yaml

REPO = Path(__file__).resolve().parent.parent
CONFIG = REPO / "web/site.config.ts"
REDIRECTS = REPO / "config/site_redirects.yaml"
OUT = REPO / "web/out"
EXPORT = REPO / "web/.snapshot"
TIMEOUT = 20.0

Get = Callable[[str], tuple[int, str]]
Head = Callable[[str], tuple[int, Mapping[str, str]]]


@dataclass(frozen=True)
class Redirects:
    gone: frozenset[str]
    renamed: Mapping[str, str]


def site_url(config_text: str) -> str:
    found = re.search(r'^export const SITE_URL = "([^"]+)";$', config_text, flags=re.M)
    if found is None:
        raise ValueError("web/site.config.ts SITE_URL taşımıyor")
    return found[1].rstrip("/")


def placeholder_findings(base: str) -> list[str]:
    host = httpx.URL(base).host
    if host == "" or host.endswith(".invalid"):
        return [f"SITE_URL yer tutucu ({base}) — alan adı kararı (AK4) olmadan yayın doğrulanamaz"]
    return []


def load_redirects(text: str) -> Redirects:
    document = yaml.safe_load(text) or {}
    if not isinstance(document, dict) or set(document) != {"gone", "renamed"}:
        raise ValueError("config/site_redirects.yaml yalnız `gone` ve `renamed` taşır")
    gone, renamed = document["gone"], document["renamed"]
    if not isinstance(gone, list) or not isinstance(renamed, dict):
        raise ValueError("`gone` liste, `renamed` eşleme olmalı")
    return Redirects(frozenset(map(str, gone)), {str(k): str(v) for k, v in renamed.items()})


def slug_index(text: str) -> tuple[set[str], set[str]]:
    document: Any = json.loads(text)
    if not isinstance(document, dict) or document.get("version") != 1:
        raise ValueError("slugs.json sürüm 1 değil")
    return set(document["leagues"]), set(document["teams"])


def vanished_findings(previous: str, current: str, redirects: Redirects) -> list[str]:
    old_leagues, old_teams = slug_index(previous)
    new_leagues, new_teams = slug_index(current)
    findings = [
        f"kaybolan lig slug'ı kabul edilmemiş: {league} (`gone:`a yazılmalı)"
        for league in sorted(old_leagues - new_leagues)
        if league not in redirects.gone
    ]
    for team in sorted(old_teams - new_teams):
        if team.split("/", 1)[0] in redirects.gone:
            continue
        target = redirects.renamed.get(team)
        if target is None:
            findings.append(f"kaybolan takım slug'ı kabul edilmemiş: {team}")
        elif target not in new_teams:
            findings.append(f"yeniden adlandırma hedefi yeni derlemede yok: {team} → {target}")
    return findings


def first_token(text: str) -> str:
    return (text.split() or [""])[0]


def parse_headers(text: str) -> dict[str, dict[str, str]]:
    blocks: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    for line in text.splitlines():
        if not line.strip():
            continue
        if not line[0].isspace():
            current = blocks.setdefault(line.strip(), {})
        elif current is not None:
            name, _, value = line.strip().partition(":")
            current[name.strip().lower()] = value.strip()
    return blocks


def samples(blocks: Mapping[str, Mapping[str, str]]) -> list[str]:
    pages = sorted(path for path in blocks if path != "/*")
    return sorted({pages[0], pages[len(pages) // 2], pages[-1]}) if pages else []


def live_findings(base: str, out: Path, export: Path, get: Get, head: Head) -> list[str]:
    built = first_token((out / "data/snapshot.sha256").read_text(encoding="utf-8"))
    exported = first_token((export / "snapshot.sha256").read_text(encoding="utf-8"))
    findings = [] if built == exported else ["derlenmiş snapshot.sha256 dışa aktarımla aynı değil"]
    status, body = get(f"{base}/data/snapshot.sha256")
    if status != 200:
        findings.append(f"canlı /data/snapshot.sha256 okunamadı (HTTP {status})")
    elif first_token(body) != built:
        findings.append("canlı /data/snapshot.sha256 derlenmiş olanla eşit değil")
    blocks = parse_headers((out / "_headers").read_text(encoding="utf-8"))
    noindex = blocks.get("/*", {}).get("x-robots-tag") == "noindex"
    for path in samples(blocks):
        status, headers = head(f"{base}{path}")
        live = {name.lower(): value for name, value in headers.items()}
        if status != 200:
            findings.append(f"{path}: HTTP {status}")
            continue
        if live.get("content-security-policy") != blocks[path].get("content-security-policy"):
            findings.append(f"{path}: canlı CSP derlenmiş _headers'la aynı değil")
        if noindex and live.get("x-robots-tag") != "noindex":
            findings.append(f"{path}: canlıda X-Robots-Tag: noindex yok")
    return findings


def _get(url: str) -> tuple[int, str]:
    try:
        response = httpx.get(url, timeout=TIMEOUT, follow_redirects=True)
    except httpx.HTTPError:
        return 0, ""
    return response.status_code, response.text


def _head(url: str) -> tuple[int, Mapping[str, str]]:
    try:
        response = httpx.head(url, timeout=TIMEOUT)
    except httpx.HTTPError:
        return 0, {}
    return response.status_code, dict(response.headers)


def _slugs(args: argparse.Namespace, base: str, get: Get) -> list[str]:
    status, body = get(f"{base}/data/slugs.json")
    if args.first_publish:
        if status == 0:
            return ["site erişilemiyor (HTTP 0) — ilk yayın da erişilebilir bir site ister"]
        if status == 200:
            return ["önceki yayın var (/data/slugs.json HTTP 200) — --first-publish yanlış"]
        sys.stdout.write(f"İLK YAYIN: kaybolan-slug karşılaştırması yapılmadı (HTTP {status})\n")
        return []
    if status != 200:
        return [f"önceki yayının /data/slugs.json'ı okunamadı (HTTP {status}) — ilk yayın mı?"]
    current = (args.out / "data/slugs.json").read_text(encoding="utf-8")
    redirects = load_redirects(args.redirects.read_text(encoding="utf-8"))
    return vanished_findings(body, current, redirects)


def main(argv: Sequence[str] | None = None, get: Get = _get, head: Head = _head) -> int:
    parser = argparse.ArgumentParser(prog="site_publish")
    parser.add_argument("command", choices=("slugs", "live"))
    parser.add_argument("--first-publish", action="store_true")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--redirects", type=Path, default=REDIRECTS)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--export", type=Path, default=EXPORT)
    args = parser.parse_args(argv)
    base = site_url(args.config.read_text(encoding="utf-8"))
    findings = placeholder_findings(base)
    if not findings:
        if args.command == "slugs":
            findings = _slugs(args, base, get)
        else:
            findings = live_findings(base, args.out, args.export, get, head)
    for finding in findings:
        sys.stdout.write(f"YAYIN KAPISI: {finding}\n")
    sys.stdout.write(f"site_publish {args.command}: {len(findings)} bulgu\n")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
