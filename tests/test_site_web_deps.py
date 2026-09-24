"""H5a: web tarafının bağımlılık listesi sabit; Node DB'ye bağlanamaz (spec §2 H5, §13).

Çalışma zamanı bağımlılığı YALNIZ `next`, `react`, `react-dom`. Dev araçları izinli
listeden. Kilit dosyasının TAMAMINDA (geçişli bağımlılıklar dahil) DB sürücüsü ve
Supabase istemcisi yok. Bağımlılık eklemek bilinçli bir commit'tir: bu dosyadaki liste
de değişir ve inceleme görür.
"""

from __future__ import annotations

import json
import re
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

DECLARED_SECTIONS = ("dependencies", "devDependencies")
# pnpm bunları da çözer/kurar; izin listesi yalnız yukarıdaki iki bölüme bakar, bu yüzden hiçbiri
# package.json'da bulunmaz (inceleme I1: `optionalDependencies` ile allowlist atlanıyordu).
UNDECLARED_SECTIONS = {
    "optionalDependencies",
    "peerDependencies",
    "peerDependenciesMeta",
    "bundleDependencies",
    "bundledDependencies",
    "overrides",
    "resolutions",
}
EXACT_VERSION = re.compile(r"\d+\.\d+\.\d+")
# pnpm 10.34.5'in kendi `DEPS_BUILD_CONFIG_KEYS` listesi (dist/pnpm.cjs). `neverBuiltDependencies`
# ayarlanınca pnpm geri kalan HER bağımlılığın betiğini koşar; o da açıcıdır.
BUILD_KEYS = {
    "dangerouslyAllowAllBuilds",
    "onlyBuiltDependencies",
    "onlyBuiltDependenciesFile",
    "neverBuiltDependencies",
    "allowBuilds",
}
GUARD_TEST = "scripts/toolchain.test.ts"


def _package() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(PACKAGE.read_text(encoding="utf-8"))
    return data


def _lock() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(LOCK.read_text(encoding="utf-8"))
    return data


def lock_package_name(key: str) -> str:
    """`ad@sürüm`: sürüm `@` taşıyabilir (git URL), ad taşıyamaz; kapsamlı adın `@`i baştadır."""
    return key[: key.index("@", 1)]


def lock_package_names(text: str) -> set[str]:
    """pnpm kilit v9 `packages:` anahtarları `ad@sürüm`dür."""
    packages = yaml.safe_load(text).get("packages") or {}
    return {lock_package_name(key) for key in packages}


def _normalized(key: str) -> str:
    """`.npmrc` kebab-case (`only-built-dependencies[]`), YAML camelCase yazar; aynı ayar."""
    return re.sub(r"[-_]|\[\]$", "", key.strip()).lower()


def glob_matches(glob: str, path: str) -> bool:
    """vitest `include` kalıplarının burada kullanılan alt kümesi: `**/`, `*`, `{a,b}`."""
    pattern = re.escape(glob).replace(r"\*\*/", "(?:.*/)?").replace(r"\*", "[^/]*")
    pattern = re.sub(
        r"\\\{(.*?)\\\}", lambda m: "(?:" + m.group(1).replace(",", "|") + ")", pattern
    )
    return re.fullmatch(pattern, path) is not None


def test_runtime_dependencies_are_exactly_next_and_react() -> None:
    assert set(_package()["dependencies"]) == RUNTIME


def test_dev_dependencies_stay_inside_the_allow_list() -> None:
    extra = set(_package()["devDependencies"]) - DEV_ALLOWED
    assert not extra, f"izin listesi dışı dev bağımlılığı: {sorted(extra)}"


def test_no_other_dependency_section_bypasses_the_allow_list() -> None:
    present = sorted(UNDECLARED_SECTIONS & set(_package()))
    assert not present, f"izin listesinin görmediği bağımlılık bölümü: {present}"


def test_lock_importer_matches_package_json_exactly() -> None:
    """Kilidin kökü package.json'la aynı adları aynı belirteçlerle taşır (install koşulmuş)."""
    lock = _lock()
    assert set(lock["importers"]) == {"."}, f"beklenmeyen ithalatçı: {sorted(lock['importers'])}"
    importer: dict[str, dict[str, dict[str, str]]] = lock["importers"]["."]
    assert set(importer) <= set(DECLARED_SECTIONS), f"kilitte ek bölüm: {sorted(importer)}"
    assert set(importer.get("dependencies", {})) == RUNTIME
    assert set(importer.get("devDependencies", {})) <= DEV_ALLOWED
    package = _package()
    for section in DECLARED_SECTIONS:
        locked = {name: entry["specifier"] for name, entry in importer.get(section, {}).items()}
        assert locked == package[section], (
            f"{section}: kilit {locked} ≠ package.json {package[section]}"
        )


@pytest.mark.parametrize("section", ["dependencies", "devDependencies"])
def test_versions_are_pinned_exactly(section: str) -> None:
    loose = {n: s for n, s in _package()[section].items() if not EXACT_VERSION.fullmatch(s)}
    assert not loose, f"tam sürüm değil: {loose}"


def test_lock_parser_reads_scoped_and_plain_names() -> None:
    text = (
        "packages:\n  '@supabase/ssr@0.1.0':\n    {}\n  pg@8.0.0:\n    {}\n"
        "  pg-native@git+ssh://git@github.com/x/y.git#abc123:\n    {}\n"
        "  '@neondatabase/serverless@https://u@example.invalid/n.tgz':\n    {}\n"
    )
    assert lock_package_names(text) == {
        "@supabase/ssr",
        "pg",
        "pg-native",
        "@neondatabase/serverless",
    }


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
    """pnpm 10 bağımlılık betiklerini varsayılan olarak koşmaz; izin listesi boş kalır.

    Ayar üç yerden okunur: package.json `pnpm`, `pnpm-workspace.yaml`, `.npmrc` — `web/` ve (pnpm
    çalışma alanı kökünü yukarıda arar) depo kökü. Kullanıcı düzeyi `~/.npmrc` depo dışıdır.
    """
    assert "pnpm" not in _package(), "package.json `pnpm` ayarı taşıyor"
    banned = {_normalized(key) for key in BUILD_KEYS}
    for directory in (WEB, REPO):
        keys: list[str] = []
        workspace = directory / "pnpm-workspace.yaml"
        if workspace.exists():
            keys += list(yaml.safe_load(workspace.read_text(encoding="utf-8")) or {})
        npmrc = directory / ".npmrc"
        if npmrc.exists():
            lines = npmrc.read_text(encoding="utf-8").splitlines()
            keys += [
                line.split("=", 1)[0] for line in lines if line.strip()[:1] not in ("", "#", ";")
            ]
        opened = sorted(key for key in keys if _normalized(key) in banned)
        assert not opened, f"bağımlılık betikleri açılmış ({directory.relative_to(REPO)}): {opened}"


def test_glob_matcher_reads_the_patterns_vitest_config_uses() -> None:
    assert glob_matches("scripts/**/*.test.ts", "scripts/toolchain.test.ts")
    assert glob_matches("scripts/**/*.test.ts", "scripts/lib/a.test.ts")
    assert glob_matches("src/**/*.test.{ts,tsx}", "src/lib/Fe.test.tsx")
    assert not glob_matches("src/**/*.test.{ts,tsx}", "scripts/toolchain.test.ts")
    assert not glob_matches("scripts/*.test.ts", "scripts/lib/a.test.ts")


def test_vitest_still_collects_the_pnpm_guard() -> None:
    """pnpm-10 bekçisi (`web/scripts/toolchain.test.ts`) vitest kapsamından düşmez (M4)."""
    assert (WEB / GUARD_TEST).is_file(), f"{GUARD_TEST} yok"
    config = (WEB / "vitest.config.ts").read_text(encoding="utf-8")
    include = re.search(r"\binclude:\s*\[(.*?)\]", config, re.S)
    assert include, "vitest.config.ts `include` okunamadı"
    globs = re.findall(r'"([^"]+)"', include.group(1))
    assert any(glob_matches(glob, GUARD_TEST) for glob in globs), f"bekçi kapsam dışı: {globs}"
    exclude = re.search(r"\bexclude:\s*\[(.*?)\]", config, re.S)
    dropped = re.findall(r'"([^"]+)"', exclude.group(1)) if exclude else []
    assert not any(glob_matches(glob, GUARD_TEST) for glob in dropped), f"bekçi dışlandı: {dropped}"


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
