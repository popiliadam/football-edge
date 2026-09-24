"""`web/netlify.toml`: hazır, bağlı değil (spec §11, B8, B9, AK16).

Netlify tarafında derleme reddedilir; başlık ve yönlendirme bu dosyada değil, derlemenin
ürettiği `out/_headers` / `out/_redirects`te (tek kaynak). Dosya secret ve ortam taşımaz.
"""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
NETLIFY = REPO / "web/netlify.toml"
# Komut birebir sabittir: "burada başarısız olması" yetmez. Depo kökünde `package.json` yok;
# `…; pnpm run build` gibi bir ek burada da düşerdi, ama Netlify'ın `web/` tabanında derlemeyi
# gerçekten denerdi.
REFUSAL = (
    "echo 'Netlify tarafinda derleme yapilmaz: yayin yalniz site.yml hazir dizini"
    " (spec 11, AK16)' >&2; exit 1"
)


def _config() -> dict[str, Any]:
    return tomllib.loads(NETLIFY.read_text(encoding="utf-8"))


def test_only_the_build_table_with_publish_and_command() -> None:
    config = _config()
    assert set(config) == {"build"}, "başlık/yönlendirme/ortam netlify.toml'a girmez (B8)"
    assert set(config["build"]) == {"publish", "command"}
    assert config["build"]["publish"] == "out"
    assert config["build"]["command"] == REFUSAL


def test_a_netlify_side_build_refuses_by_name() -> None:
    result = subprocess.run(
        ["bash", "-c", _config()["build"]["command"]],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "derleme yapilmaz" in result.stderr
