"""İş akışı testlerinin paylaştığı okuyucular: workflow YAML'ı ve migration SQL'i.

Yalnız OKUR, iddia kurmaz. İddialar `test_workflows.py`, `test_collect_workflows.py` ve
`test_seal_anchor_step.py`de.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parent.parent
SEAL = REPO / ".github/workflows/seal.yml"
MIGRATIONS = REPO / "db/migrations"
COLLECT_DAILY = REPO / ".github/workflows/collect-daily.yml"
COLLECT_NEWS = REPO / ".github/workflows/collect-news.yml"
# Her toplayıcı workflow'u ve sırayla koşturduğu `football_edge.collect` alt komutları.
COLLECTORS = {
    COLLECT_DAILY: ("fetch-footystats", "fetch-tff", "fetch-venues"),
    COLLECT_NEWS: ("fetch-news",),
}


def _steps(path: Path) -> list[dict[str, Any]]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    (job,) = document["jobs"].values()
    return list(job["steps"])


def _index_of(steps: list[dict[str, Any]], needle: str, key: str = "run") -> int | None:
    for index, step in enumerate(steps):
        if needle in str(step.get(key, "")):
            return index
    return None


def _triggers(path: Path) -> dict[str, Any]:
    """Tetikleyicileri döner.

    PyYAML (YAML 1.1) `on:` anahtarını BOOLEAN True'ya çevirir — `document["on"]`
    KeyError verir. Bu tuzak sessizce "tetik yok" sonucunu üretir, o yüzden iki
    yazım da kabul edilir.
    """
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    return dict(document.get("on") or document.get(True) or {})


def _migrations() -> dict[str, str]:
    texts = {
        path.name: path.read_text(encoding="utf-8") for path in sorted(MIGRATIONS.glob("*.sql"))
    }
    assert texts, "db/migrations/*.sql bulunamadı — aşağıdaki taramalar boş geçerdi"
    return texts


def _dispatch_targets(sql: str) -> set[str]:
    """Bir migration'ın tetikleyebildiği workflow'lar: URL'e gömülü hedef (0003) ya da URL'i
    kuran fonksiyonun izinli listesi (0004: `array['seal.yml', ...]`)."""
    in_urls = re.findall(r"/actions/workflows/([\w.-]+)/dispatches", sql)
    in_lists = [
        name
        for listed in re.findall(r"array\[([^\]]*)\]", sql)
        for name in re.findall(r"'([\w.-]+\.ya?ml)'", listed)
    ]
    return {*in_urls, *in_lists}


def _functions() -> dict[str, str]:
    """`ops.<ad>` → yürürlükteki gövdesi. Migration'lar ad sırasıyla uygulanır ve `create or
    replace` öncekini ezer: aynı adın son tanımı kazanır."""
    return {
        name: body
        for sql in _migrations().values()
        for name, body in re.findall(
            r"create or replace function ops\.(\w+)\([^)]*\).*?\$\$(.*?)\$\$", sql, flags=re.S
        )
    }


def _allow_list() -> set[str]:
    """`ops.dispatch_workflow`un yürürlükteki izinli listesi: her tanım listeyi BAŞTAN yazar."""
    return _dispatch_targets(_functions()["dispatch_workflow"])


def _cron_jobs() -> dict[str, tuple[str, str]]:
    """pg_cron iş adı → yürürlükteki (zamanlama, komut). Aynı adla yeniden zamanlamak işi
    günceller: migration sırasında son çağrı kazanır."""
    return {
        job: (spec, command)
        for sql in _migrations().values()
        for job, spec, command in re.findall(
            r"cron\.schedule\(\s*'([\w-]+)',\s*'([^']+)',\s*'([^']+)'\s*\)", sql
        )
    }
