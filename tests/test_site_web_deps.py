"""H5a: web tarafının bağımlılık listesi sabit; Node DB'ye bağlanamaz (spec §2 H5, §13).

Çalışma zamanı bağımlılığı YALNIZ `next`, `react`, `react-dom`. Dev araçları izinli
listeden. Kilit dosyasının TAMAMINDA (geçişli bağımlılıklar dahil) DB sürücüsü ve
Supabase istemcisi yok. Bağımlılık eklemek bilinçli bir commit'tir: bu dosyadaki liste
de değişir ve inceleme görür.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
WEB = REPO / "web"
PACKAGE = WEB / "package.json"
LOCK = WEB / "pnpm-lock.yaml"

RUNTIME = {"next", "react", "react-dom"}
# Spec §13'ün dev listesi + `@types/react-dom` (react-dom/server tipleri; plan kararı, yalnız tip).
DEV_ALLOWED = {
    "typescript",
    "@types/react",
    "@types/react-dom",
    "@types/node",
    "vitest",
    "@biomejs/biome",
    "schema-dts",
}
# Geçişli dahil hiçbir yerde olmayacaklar: DB sürücüleri, ORM'ler, Supabase istemcileri.
BANNED = {
    "pg",
    "pg-native",
    "postgres",
    "@neondatabase/serverless",
    "mysql",
    "mysql2",
    "better-sqlite3",
    "sqlite3",
    "prisma",
    "@prisma/client",
    "drizzle-orm",
    "kysely",
    "knex",
    "sequelize",
    "typeorm",
    "netlify-cli",
}
BANNED_SCOPES = ("@supabase/",)


def _package() -> dict[str, Any]:
    return json.loads(PACKAGE.read_text(encoding="utf-8"))


def lock_package_names(text: str) -> set[str]:
    """pnpm kilit v9 `packages:` anahtarları `ad@sürüm`dür; kapsamlı ad `@` ile başlar."""
    packages = yaml.safe_load(text).get("packages") or {}
    return {key[: key.rindex("@")] for key in packages}


def test_runtime_dependencies_are_exactly_next_and_react() -> None:
    assert set(_package()["dependencies"]) == RUNTIME


def test_dev_dependencies_stay_inside_the_allow_list() -> None:
    extra = set(_package()["devDependencies"]) - DEV_ALLOWED
    assert not extra, f"izin listesi dışı dev bağımlılığı: {sorted(extra)}"


@pytest.mark.parametrize("section", ["dependencies", "devDependencies"])
def test_versions_are_pinned_exactly(section: str) -> None:
    loose = {name: spec for name, spec in _package()[section].items() if not spec[:1].isdigit()}
    assert not loose, f"tam sürüm değil: {loose}"


def test_lock_parser_reads_scoped_and_plain_names() -> None:
    text = "packages:\n  '@supabase/ssr@0.1.0':\n    {}\n  pg@8.0.0:\n    {}\n"
    assert lock_package_names(text) == {"@supabase/ssr", "pg"}


def test_no_database_client_anywhere_in_the_lockfile() -> None:
    names = lock_package_names(LOCK.read_text(encoding="utf-8"))
    assert {"next", "react", "react-dom"} <= names, "kilit ayrıştırılamadı"
    leaking = sorted(name for name in names if name in BANNED or name.startswith(BANNED_SCOPES))
    assert not leaking, f"DB/Supabase istemcisi kilitte (H5): {leaking}"


def test_toolchain_is_pinned_where_ci_reads_it() -> None:
    package = _package()
    assert (WEB / ".nvmrc").read_text(encoding="utf-8").strip() == "24"
    assert package["engines"] == {"node": ">=24 <25"}
    assert package["packageManager"].startswith("pnpm@10.")
    assert package["type"] == "module"


def test_dependency_lifecycle_scripts_stay_closed() -> None:
    """pnpm 10 bağımlılık betiklerini varsayılan olarak koşmaz; izin listesi boş kalır."""
    assert "pnpm" not in _package(), "package.json `pnpm` ayarı taşıyor"
    workspace = WEB / "pnpm-workspace.yaml"
    if workspace.exists():
        settings = yaml.safe_load(workspace.read_text(encoding="utf-8")) or {}
        opened = {"onlyBuiltDependencies", "dangerouslyAllowAllBuilds"} & set(settings)
        assert not opened, f"bağımlılık betikleri açılmış: {sorted(opened)}"


@pytest.mark.parametrize(
    "path",
    [
        "web/node_modules/x",
        "web/.next/x",
        "web/out/x",
        "web/.snapshot/x",
        "web/next-env.d.ts",
        "web/tsconfig.tsbuildinfo",
    ],
)
def test_build_output_never_enters_git(path: str) -> None:
    result = subprocess.run(["git", "check-ignore", "-q", path], cwd=REPO, check=False)
    assert result.returncode == 0, f"{path} gitignore'da değil"
