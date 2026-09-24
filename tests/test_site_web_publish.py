"""`scripts/site_publish.py`: yayından önce kaybolan-slug, yayından sonra yayımlanan = doğrulanan.

Ağ yoktur: `get`/`head` sahtedir. Dosyalar geçici dizinde kurulur (spec §11, §6.4/3f, AK20 b).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parent.parent


def _load() -> ModuleType:
    """`scripts/` bir paket değil: workflow'un koştuğu dosya kendi yolundan yüklenir."""
    spec = importlib.util.spec_from_file_location("site_publish", REPO / "scripts/site_publish.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclass modülünü sys.modules'ta arar
    spec.loader.exec_module(module)
    return module


site_publish = _load()
BASE = "https://site.example"
CSP = "default-src 'self'; script-src 'self' 'sha256-A='"
HEX = "a" * 64


def _slugs(leagues: list[str], teams: list[str]) -> str:
    return json.dumps({"version": 1, "leagues": leagues, "teams": teams})


PREVIOUS = _slugs(["alpha", "beta"], ["alpha/kuzey", "alpha/guney", "beta/delta"])


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    (tmp_path / "out/data").mkdir(parents=True)
    (tmp_path / "export").mkdir()
    (tmp_path / "site.config.ts").write_text(f'export const SITE_URL = "{BASE}";\n', "utf-8")
    (tmp_path / "redirects.yaml").write_text("gone: []\nrenamed: {}\n", encoding="utf-8")
    (tmp_path / "out/data/slugs.json").write_text(PREVIOUS, encoding="utf-8")
    (tmp_path / "out/data/snapshot.sha256").write_text(f"{HEX}\n", encoding="utf-8")
    (tmp_path / "export/snapshot.sha256").write_text(f"{HEX}  snapshot.json\n", encoding="utf-8")
    headers = f"/*\n  X-Robots-Tag: noindex\n\n/en/\n  Content-Security-Policy: {CSP}\n"
    (tmp_path / "out/_headers").write_text(headers, encoding="utf-8")
    return tmp_path


def _run(tree: Path, *args: str, get: object, head: object = None) -> int:
    paths = ["--config", str(tree / "site.config.ts"), "--redirects", str(tree / "redirects.yaml")]
    paths += ["--out", str(tree / "out"), "--export", str(tree / "export")]
    result: int = site_publish.main([*args, *paths], get=get, head=head)
    return result


def _serving(slugs: str | None, status: int = 200) -> object:
    return lambda url: (status, slugs or "") if url == f"{BASE}/data/slugs.json" else (404, "")


def test_site_url_is_read_from_the_single_config() -> None:
    assert site_publish.site_url('export const SITE_URL = "https://x.test/";\n') == "https://x.test"


def test_unchanged_slugs_pass(tree: Path) -> None:
    assert _run(tree, "slugs", get=_serving(PREVIOUS)) == 0


def test_a_vanished_team_without_acknowledgement_is_red(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    current = _slugs(["alpha", "beta"], ["alpha/kuzey", "beta/delta"])
    (tree / "out/data/slugs.json").write_text(current, encoding="utf-8")
    assert _run(tree, "slugs", get=_serving(PREVIOUS)) == 1
    assert "kaybolan takım slug'ı kabul edilmemiş: alpha/guney" in capsys.readouterr().out


def test_a_rename_passes_only_when_its_target_exists(tree: Path) -> None:
    current = _slugs(["alpha", "beta"], ["alpha/kuzey", "alpha/guney-yeni", "beta/delta"])
    (tree / "out/data/slugs.json").write_text(current, encoding="utf-8")
    redirects = tree / "redirects.yaml"
    redirects.write_text('gone: []\nrenamed: {"alpha/guney": "alpha/guney-yeni"}\n', "utf-8")
    assert _run(tree, "slugs", get=_serving(PREVIOUS)) == 0
    redirects.write_text('gone: []\nrenamed: {"alpha/guney": "alpha/yok"}\n', "utf-8")
    assert _run(tree, "slugs", get=_serving(PREVIOUS)) == 1


def test_a_vanished_league_is_red_even_without_teams(tree: Path) -> None:
    previous = _slugs(["alpha", "beta", "gamma"], ["alpha/kuzey", "alpha/guney", "beta/delta"])
    assert _run(tree, "slugs", get=_serving(previous)) == 1
    (tree / "redirects.yaml").write_text("gone: [gamma]\nrenamed: {}\n", encoding="utf-8")
    assert _run(tree, "slugs", get=_serving(previous)) == 0


def test_a_gone_league_covers_its_teams(tree: Path) -> None:
    current = _slugs(["alpha"], ["alpha/kuzey", "alpha/guney"])
    (tree / "out/data/slugs.json").write_text(current, encoding="utf-8")
    assert _run(tree, "slugs", get=_serving(PREVIOUS)) == 1
    (tree / "redirects.yaml").write_text("gone: [beta]\nrenamed: {}\n", encoding="utf-8")
    assert _run(tree, "slugs", get=_serving(PREVIOUS)) == 0


@pytest.mark.parametrize("status", [0, 404, 500])
def test_an_unreadable_previous_publication_is_red(tree: Path, status: int) -> None:
    assert _run(tree, "slugs", get=_serving(None, status)) == 1


def test_first_publish_passes_only_when_there_is_no_previous_publication(tree: Path) -> None:
    assert _run(tree, "slugs", "--first-publish", get=_serving(None, 404)) == 0
    assert _run(tree, "slugs", "--first-publish", get=_serving(PREVIOUS)) == 1


def test_first_publish_is_red_when_the_site_is_unreachable(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Spec §11/AK20 b: erişilemeyen site kırmızıdır — ilk yayında da."""
    assert _run(tree, "slugs", "--first-publish", get=_serving(None, 0)) == 1
    assert "site erişilemiyor" in capsys.readouterr().out


@pytest.mark.parametrize("command", ["slugs", "live"])
def test_a_placeholder_domain_is_red_without_touching_the_network(tree: Path, command: str) -> None:
    config = 'export const SITE_URL = "https://example.invalid";\n'
    (tree / "site.config.ts").write_text(config, encoding="utf-8")

    def offline(url: str) -> tuple[int, str]:
        raise AssertionError(f"yer tutucu adresle ağa çıkıldı: {url}")

    args = ("--first-publish",) if command == "slugs" else ()
    assert _run(tree, command, *args, get=offline, head=offline) == 1


def test_the_committed_site_config_is_still_a_placeholder() -> None:
    """Bugün AK4 kararı yok: depodaki SITE_URL iki kapıyı da kırmızı tutar (bilerek)."""
    base = site_publish.site_url((REPO / "web/site.config.ts").read_text("utf-8"))
    assert site_publish.placeholder_findings(base) != []


def test_the_redirects_file_shape_is_strict() -> None:
    with pytest.raises(ValueError, match="yalnız `gone` ve `renamed`"):
        site_publish.load_redirects("gone: []\nrenamed: {}\nextra: 1\n")


def test_the_committed_redirects_file_loads() -> None:
    loaded = site_publish.load_redirects((REPO / "config/site_redirects.yaml").read_text("utf-8"))
    assert loaded.gone == frozenset() and dict(loaded.renamed) == {}


def _live(sha: str = HEX, csp: str = CSP, robots: str | None = "noindex") -> tuple[object, object]:
    def get(url: str) -> tuple[int, str]:
        return (200, f"{sha}\n") if url == f"{BASE}/data/snapshot.sha256" else (404, "")

    def head(url: str) -> tuple[int, Mapping[str, str]]:
        headers = {"Content-Security-Policy": csp}
        if robots is not None:
            headers["X-Robots-Tag"] = robots
        return (200, headers) if url == f"{BASE}/en/" else (404, {})

    return get, head


def test_published_equals_verified_passes(tree: Path) -> None:
    get, head = _live()
    assert _run(tree, "live", get=get, head=head) == 0


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"sha": "b" * 64}, "canlı /data/snapshot.sha256 derlenmiş olanla eşit değil"),
        ({"csp": "default-src *"}, "canlı CSP derlenmiş _headers'la aynı değil"),
        ({"robots": None}, "canlıda X-Robots-Tag: noindex yok"),
    ],
)
def test_a_live_mismatch_is_red(
    tree: Path, capsys: pytest.CaptureFixture[str], change: dict[str, object], message: str
) -> None:
    get, head = _live(**change)  # type: ignore[arg-type]
    assert _run(tree, "live", get=get, head=head) == 1
    assert message in capsys.readouterr().out


def test_the_built_hash_must_match_the_export(tree: Path) -> None:
    (tree / "export/snapshot.sha256").write_text(f"{'c' * 64}  snapshot.json\n", "utf-8")
    get, head = _live()
    assert _run(tree, "live", get=get, head=head) == 1
