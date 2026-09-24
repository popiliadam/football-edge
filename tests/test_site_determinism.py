"""B12 §5.1/5: ikinci türetim ayrı süreçte, başka `PYTHONHASHSEED`le aynı dökümden AYNI hash verir.

Kanıt olasılıklı değildir (§18.4 n3): fixture ≥ 32 farklı takım adı taşır ve iki sabit tohumla
küme sırasının GERÇEKTEN farklı olduğu önce sınanır. Mutasyon kanıtı plandadır: `_teams` sıralı
anahtar yerine bir `str` kümesi üzerinde dönerse `test_two_seeds_derive_the_same_content_hash`
kırmızı olur.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from football_edge.site import export
from football_edge.site.contract import EXIT_SITE_CUT, EXIT_SITE_NONDETERMINISTIC, content_sha256
from football_edge.site.derive import derive
from football_edge.site.export import ExportRefused, derive_in_subprocess
from football_edge.site.inputs import load_inputs
from tests.site_builders import DUMP_CORRUPTIONS, EVEN, Round, export_dump

REPO = Path(__file__).resolve().parent.parent
TEAMS = [f"Takım {chr(0x41 + index % 26)}{index:02d}" for index in range(34)]
LEAGUE = ("tst.1", "Deneme Ligi", "Testland", "deneme-ligi")


def _dump() -> str:
    matches, rounds = [], []
    for number in range(len(TEAMS) // 2):
        match_id = f"{number:02d}" + "cd" * 15
        home, away = TEAMS[2 * number], TEAMS[2 * number + 1]
        matches.append((match_id, "tst.1", f"2026-09-2{number % 10}T18:00:00Z", home, away))
        rounds.append(Round(match_id, "2026-09-19T08:00:00Z", home, away, [EVEN] * 3))
    return export_dump(leagues=[LEAGUE], matches=matches, rounds=rounds)


@pytest.fixture(autouse=True)
def _child_imports_this_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYTHONPATH", str(REPO / "src"))


def _set_order(seed: str) -> str:
    """`_teams`in anahtar yapısı: (lig, slug) demetlerinin KÜMESİ bu tohumla hangi sırada döner."""
    probe = (
        "import sys\n"
        "from football_edge.site.slugs import slugify\n"
        "print('|'.join(repr(key) for key in {('tst.1', slugify(n)) for n in sys.argv[1:]}))"
    )
    env = {**os.environ, "PYTHONHASHSEED": seed}
    result = subprocess.run(
        [sys.executable, "-c", probe, *TEAMS], capture_output=True, text=True, env=env, check=True
    )
    return result.stdout


def test_the_two_fixed_seeds_really_order_the_fixture_team_set_differently() -> None:
    """Önkoşul: bu olmadan aşağıdaki eşitlik bir küme hatasını yakalayamazdı."""
    assert len(set(TEAMS)) >= 32
    assert _set_order("1") != _set_order("2")


def test_two_seeds_derive_the_same_content_hash() -> None:
    dump = _dump()
    local = content_sha256(derive(load_inputs(dump)))

    assert derive_in_subprocess(dump, hash_seed="1") == local
    assert derive_in_subprocess(dump, hash_seed="2") == local


def test_a_crashing_child_is_named_and_its_output_is_not_relayed() -> None:
    """n4: çocuğun traceback'i bir fiyat taşıyabilir; ana süreç yalnız adlandırılmış hata verir.

    Çocuk bozuk dökümde traceback'le 1 değil, adlandırılmış 22 ile çıkar (`derive-stdin`).
    """
    poisoned = _dump().replace('"4.0"', '"4.47x"', 1)

    with pytest.raises(ExportRefused) as refused:
        derive_in_subprocess(poisoned, hash_seed="1")

    assert refused.value.code == EXIT_SITE_NONDETERMINISTIC
    assert str(refused.value) == f"ikinci türetim alt süreci düştü, çıkış kodu {EXIT_SITE_CUT}"


def test_the_child_gets_no_database_address_and_the_other_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Çocuğun ortamında DB adresi yoktur: ikinci türetim yalnız dökümden çalışır."""
    monkeypatch.setenv("SITE_DATABASE" + "_URL", "postgresql://x@127.0.0.1:1/y")
    monkeypatch.setenv("DATABASE" + "_URL", "postgresql://x@127.0.0.1:1/y")
    seen: list[dict[str, str]] = []

    def spy(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen.append(kwargs["env"])
        return subprocess.CompletedProcess(args, 0, stdout="0" * 64 + "\n", stderr="")

    monkeypatch.setattr(export.subprocess, "run", spy)

    assert export.derive_in_subprocess("{}", hash_seed="1") == "0" * 64
    assert "SITE_DATABASE" + "_URL" not in seen[0] and "DATABASE" + "_URL" not in seen[0]
    assert seen[0]["PYTHONHASHSEED"] == "1"


def test_a_child_that_never_finishes_is_named(monkeypatch: pytest.MonkeyPatch) -> None:
    """m6: zaman aşımı traceback'le exit 1 değil, adlandırılmış belirlenimcilik kırmızısı (23)."""

    def hang(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(args, kwargs["timeout"])

    monkeypatch.setattr(export.subprocess, "run", hang)

    with pytest.raises(ExportRefused, match="300 sn'de bitmedi") as refused:
        export.derive_in_subprocess("{}", hash_seed="1")
    assert refused.value.code == EXIT_SITE_NONDETERMINISTIC


@pytest.mark.parametrize(("old", "new", "kind"), DUMP_CORRUPTIONS)
def test_derive_stdin_names_an_undecodable_dump_by_class_only(
    old: str, new: str, kind: str
) -> None:
    """Çocuk da bozuk dökümde traceback'le 1 değil, 22 ve yalnız sınıf adıyla çıkar."""
    dump = _dump()
    assert old in dump, f"bozma çapası yok: {old!r}"

    result = subprocess.run(
        [sys.executable, "-m", "football_edge.site", "derive-stdin"],
        input=dump.replace(old, new, 1),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONHASHSEED": "1"},
        check=False,
        timeout=300,
    )

    assert result.returncode == EXIT_SITE_CUT
    assert result.stdout == f"İKİNCİ TÜRETİM REDDEDİLDİ: girdi dökümü çözülemedi ({kind})\n"
    assert result.stderr == ""
