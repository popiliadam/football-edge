"""`scripts/robots_drift.py --refresh`: aynı kalan robots.txt, doğrulama tarihini tazeler.

Kapı (`sources.audit_offline`) her etkin kaynağın `robots_verified_at`inin ≤30 gün olmasını ister.
Tarihi bot çeker, ama yalnız canlısı ölçülüp anlık görüntüyle aynı bulunan kaynağın ve yalnız o
değeri: sapan ya da ölçülemeyen kaynağın tarihi yerinde kalır, tur kırmızı verir. Ağa çıkılmaz
(`httpx.MockTransport`); betik workflow adımının çağırdığı yoldan — `main(argv)` — sınanır.
"""

from __future__ import annotations

import dataclasses
import errno
import importlib.util
import io
import re
import shutil
import stat
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta, timezone
from pathlib import Path
from types import ModuleType
from typing import IO, Any
from urllib.parse import urlsplit

import httpx
import pytest

from football_edge.sources import load_sources

REPO = Path(__file__).resolve().parent.parent
REGISTRY = Path("config/sources.yaml")
TODAY = date(2026, 10, 15)
NOW = datetime.combine(TODAY, time(12), tzinfo=UTC)
STALE = TODAY - timedelta(days=8)
FRESH = TODAY - timedelta(days=3)
ALPHA_ROBOTS = "User-agent: *\nDisallow: /private\n"
BETA_ROBOTS = "User-agent: *\nDisallow: /\n"

Live = Callable[[httpx.Request], httpx.Response]


def _load_script() -> ModuleType:
    """`scripts/` bir paket değil: workflow'un koştuğu dosya kendi yolundan yüklenir."""
    spec = importlib.util.spec_from_file_location("robots_drift", REPO / "scripts/robots_drift.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


robots_drift = _load_script()


def _registry(alpha: date, beta: date) -> str:
    """Gerçek `config/sources.yaml`in biçimi: başlık yorumu, katlanmış not, akış listesi.

    Yorum ve not da tarih taşır: tazeleme onlara dokunursa bayt karşılaştırması yakalar.
    """
    return f"""\
# Kayıt defteri — robots_verified_at: {STALE} (yorumdaki tarih değişmemeli)
sources:
  - id: alpha
    base_url: https://alpha.example
    user_agent: football-edge/0.1
    crawl_delay_seconds: 1.0
    robots_verified_at: {alpha}
    declared_paths: ['/a']
    enabled: true
    access_basis: robots
    terms_url: ''
    note: >-
      Katlanmış not, ikinci satırı tarih taşır:
      robots_verified_at: {STALE} elle yazılmıştı.

  - id: beta
    base_url: https://beta.example
    user_agent: football-edge/0.1
    crawl_delay_seconds: 1.0
    robots_verified_at: {beta}
    declared_paths: []
    enabled: false
    access_basis: robots
    terms_url: ''
    note: kapalı kaynak
"""


def _same(body: str) -> Live:
    return lambda request: httpx.Response(200, text=body)


def _status(code: int) -> Live:
    return lambda request: httpx.Response(code, text="yanıt gövdesi")


def _unreachable(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("bağlantı kurulamadı", request=request)


def _serve(live: dict[str, Live]) -> httpx.MockTransport:
    """Host başına canlı robots.txt; tanımadığı istek testi düşürür (sessiz geçmez)."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/robots.txt", request.url
        return live[str(request.url.host)](request)

    return httpx.MockTransport(handler)


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Betik `config/` yollarını çalışma dizininden okur — workflow onu depo kökünde koşar."""
    robots = tmp_path / "config/robots"
    robots.mkdir(parents=True)
    (robots / "alpha.txt").write_text(ALPHA_ROBOTS, encoding="utf-8")
    (robots / "beta.txt").write_text(BETA_ROBOTS, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _run(original: str, live: dict[str, Live], argv: list[str] | None = None) -> tuple[int, bytes]:
    """Kayıt defterini yazar, betiği koşar; (çıkış kodu, dosyanın son baytları) döner."""
    REGISTRY.write_text(original, encoding="utf-8")
    code = robots_drift.main(
        ["--refresh"] if argv is None else argv, transport=_serve(live), now=NOW
    )
    return code, REGISTRY.read_bytes()


@pytest.mark.parametrize(
    ("snapshot", "live"),
    [
        (ALPHA_ROBOTS, _same(ALPHA_ROBOTS)),
        # understat CRLF döndürüyor: satır sonu stili sapma değildir, tazelemeyi de engellemez.
        (ALPHA_ROBOTS, _same(ALPHA_ROBOTS.replace("\n", "\r\n"))),
        # tff: robots.txt yok (404) — ölçülmüş, boş politika; ölçülemedi değil.
        ("", _status(404)),
    ],
    ids=["aynı-gövde", "crlf-aynı-gövde", "404-politika-yok"],
)
def test_unchanged_robots_older_than_a_week_moves_only_its_own_date_to_today(
    workspace: Path, snapshot: str, live: Live
) -> None:
    (workspace / "config/robots/alpha.txt").write_text(snapshot, encoding="utf-8")

    code, after = _run(
        _registry(alpha=STALE, beta=FRESH),
        {"alpha.example": live, "beta.example": _same(BETA_ROBOTS)},
    )

    assert code == 0
    assert after == _registry(alpha=TODAY, beta=FRESH).encode("utf-8"), (
        "yalnız alpha'nın robots_verified_at değeri bugüne çekilmeliydi; yorum, not ve beta "
        "bayt bayt aynı kalmalıydı"
    )


@pytest.mark.parametrize("age", [3, 7], ids=["3-gün", "tam-7-gün"])
def test_unchanged_robots_verified_within_a_week_is_left_alone(workspace: Path, age: int) -> None:
    """Her gün değil haftada bir: tazeleme bir bot commit'idir, günlük gürültü olmamalı."""
    original = _registry(alpha=TODAY - timedelta(days=age), beta=FRESH)

    code, after = _run(
        original, {"alpha.example": _same(ALPHA_ROBOTS), "beta.example": _same(BETA_ROBOTS)}
    )

    assert code == 0
    assert after == original.encode("utf-8")


def test_drifted_robots_keeps_its_date_and_fails_the_run(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    original = _registry(alpha=STALE, beta=FRESH)

    code, after = _run(
        original, {"alpha.example": _same(BETA_ROBOTS), "beta.example": _same(BETA_ROBOTS)}
    )

    assert code == 1
    assert after == original.encode("utf-8"), "sapan kaynağın tarihi tazelendi"
    assert "ROBOTS SAPMASI: alpha" in capsys.readouterr().out


@pytest.mark.parametrize("live", [_status(503), _unreachable], ids=["http-503", "bağlantı-yok"])
def test_unmeasured_robots_keeps_its_date_and_fails_the_run(
    workspace: Path, live: Live, capsys: pytest.CaptureFixture[str]
) -> None:
    """503 → `snapshot_from_status` None; bağlantı hatası → yanıt hiç yok. İkisi de ölçüm değil."""
    original = _registry(alpha=STALE, beta=FRESH)

    code, after = _run(original, {"alpha.example": live, "beta.example": _same(BETA_ROBOTS)})

    assert code == 1
    assert after == original.encode("utf-8"), "ölçülemeyen kaynağın tarihi tazelendi"
    assert "ÖLÇÜLEMEDİ: alpha" in capsys.readouterr().out


def test_a_drifting_source_does_not_hold_back_an_unchanged_ones_refresh(workspace: Path) -> None:
    """İki kaynak AYNI tarihi taşır: metinde tarih arayıp değiştiren bir düzenleme ikisini de
    çekerdi. Tur kırmızıdır ama aynı kalan kaynak yine tazelenir — tek bir sapma öbür
    kaynakların tarihini de bayatlatmamalı."""
    code, after = _run(
        _registry(alpha=STALE, beta=STALE),
        {"alpha.example": _same(ALPHA_ROBOTS), "beta.example": _same(ALPHA_ROBOTS)},
    )

    assert code == 1
    assert after == _registry(alpha=TODAY, beta=STALE).encode("utf-8")


def test_without_refresh_the_run_only_reports(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--refresh` yokken betik eskisi gibi yalnız ölçer ve raporlar; dosyaya hiç dokunmaz."""
    original = _registry(alpha=STALE, beta=STALE)

    code, after = _run(
        original, {"alpha.example": _same(ALPHA_ROBOTS), "beta.example": _same(BETA_ROBOTS)}, []
    )

    assert code == 0
    assert after == original.encode("utf-8")
    assert capsys.readouterr().out == "sapma yok: alpha\nsapma yok: beta\n"


def _duplicate_key(original: str) -> str:
    """alpha'da iki `robots_verified_at`: YAML sessizce sonuncuyu alır, hangisi düzeltilir?"""
    line = f"    robots_verified_at: {STALE}\n"
    return original.replace(line, line * 2, 1)


def _shared_anchor(original: str) -> str:
    """alpha'nın tarihi bir YAML çapası, beta'nınki onun takma adı: ikisi TEK düğümdür ve alpha
    için yapılan düzenleme sapan beta'nın tarihini de değiştirirdi."""
    anchored = original.replace(
        f"    robots_verified_at: {STALE}\n", f"    robots_verified_at: &dogrulama {STALE}\n", 1
    )
    return anchored.replace(
        f"    robots_verified_at: {FRESH}\n", "    robots_verified_at: *dogrulama\n", 1
    )


def _alpha(registry: Path) -> list[Any]:
    """`refresh`e verilecek doğrulanmış kaynak: yalnız alpha (beta sapmış sayılır)."""
    return [source for source in load_sources(registry) if source.id == "alpha"]


@pytest.mark.parametrize(
    "mangle", [_duplicate_key, _shared_anchor], ids=["yinelenen-anahtar", "paylaşılan-çapa"]
)
def test_an_ambiguous_date_is_never_guessed(tmp_path: Path, mangle: Callable[[str], str]) -> None:
    """Düzenlenecek değer tek anlamlı değilse tahmin edilmez: hiçbir şey yazılmaz ve tur düşer —
    sessizce atlanan bir tarih 30 gün sonra kapıyı kırmızıya düşürürdü. Hata, düzenlenen
    dosyanın KENDİSİNİ adlandırır (varsayılan kayıt defterini değil)."""
    registry = tmp_path / "kopya.yaml"
    original = mangle(_registry(alpha=STALE, beta=FRESH))
    assert original != _registry(alpha=STALE, beta=FRESH), "bozma işlevi hiçbir şeyi değiştirmedi"
    registry.write_text(original, encoding="utf-8")

    with pytest.raises(ValueError, match=rf"^{re.escape(str(registry))}: .*robots_verified_at"):
        robots_drift.refresh(registry, _alpha(registry), TODAY)

    assert registry.read_bytes() == original.encode("utf-8")


class _FullDisk:
    """Yazılanın yarısını diske bırakıp ENOSPC ile düşen dosya tutamacı."""

    def __init__(self, handle: IO[bytes]) -> None:
        self._handle = handle

    def write(self, data: bytes) -> int:
        self._handle.write(memoryview(data)[: len(data) // 2])
        self._handle.flush()
        raise OSError(errno.ENOSPC, "No space left on device")

    def __getattr__(self, name: str) -> Any:
        return getattr(self._handle, name)

    def __enter__(self) -> _FullDisk:
        return self

    def __exit__(self, *exc: object) -> None:
        self._handle.close()


class _ShortWrite(_FullDisk):
    """Yarısını bırakıp hata VERMEDEN dönen tutamaç: diskteki baytlar amaçlanan metin değil."""

    def write(self, data: bytes) -> int:
        half = memoryview(data)[: len(data) // 2]
        self._handle.write(half)
        return len(half)


@pytest.mark.parametrize(
    ("handle", "error"),
    [(_FullDisk, OSError), (_ShortWrite, ValueError)],
    ids=["yazma-yarıda-düşer", "yazma-sessizce-eksik"],
)
def test_a_failed_write_leaves_the_registry_byte_for_byte_intact(
    tmp_path: Path, handle: type[_FullDisk], error: type[Exception]
) -> None:
    """Commit adımı kırmızı turda da koşar: yarıda kalan bir yazma kesik kayıt defterini main'e
    götürürdü. Arıza `io.open`da taklit edilir — hem `Path.write_bytes` hem `os.fdopen` oradan
    geçer. Kayıt defteri bayt bayt aynı kalmalı, yanında geçici dosya kalmamalı."""
    registry = tmp_path / "sources.yaml"
    original = _registry(alpha=STALE, beta=FRESH)
    registry.write_text(original, encoding="utf-8")
    verified = _alpha(registry)
    real_open = io.open

    def failing_open(file: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        opened = real_open(file, mode, *args, **kwargs)
        return handle(opened) if "w" in mode else opened

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(io, "open", failing_open)
        with pytest.raises(error):
            robots_drift.refresh(registry, verified, TODAY)

    assert registry.read_bytes() == original.encode("utf-8")
    assert [path.name for path in tmp_path.iterdir()] == ["sources.yaml"], "geçici dosya kaldı"


@pytest.mark.parametrize(
    "now",
    [
        # İstanbul 01:30 = UTC'de hâlâ önceki gün: yerel gün yazılsa kapı "gelecekte" derdi.
        datetime(2030, 1, 1, 1, 30, tzinfo=timezone(timedelta(hours=3))),
        # New York 20:30 = UTC'de ertesi gün 01:30: yerel gün yazılsa tarih bir gün geride kalırdı.
        datetime(2029, 12, 31, 20, 30, tzinfo=timezone(timedelta(hours=-5))),
    ],
    ids=["yerel-gün-ileride", "yerel-gün-geride"],
)
def test_the_written_date_is_the_utc_day_the_gate_uses(workspace: Path, now: datetime) -> None:
    """Kapı (`collect sources-audit`) `datetime.now(UTC).date()` ile ölçer; bot o günü yazmalı."""
    utc_day = now.astimezone(UTC).date()
    assert utc_day != now.date(), "vaka yerel günle UTC gününü ayırmıyor"
    recent = utc_day - timedelta(days=3)
    REGISTRY.write_text(_registry(alpha=utc_day - timedelta(days=8), beta=recent), encoding="utf-8")

    code = robots_drift.main(
        ["--refresh"],
        transport=_serve(
            {"alpha.example": _same(ALPHA_ROBOTS), "beta.example": _same(BETA_ROBOTS)}
        ),
        now=now,
    )

    assert code == 0
    assert REGISTRY.read_bytes() == _registry(alpha=utc_day, beta=recent).encode("utf-8")


def test_messages_follow_the_refresh_threshold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eşik tek yerde yaşar: `REFRESH_AFTER` değişirse mesaj ve yardım metni eskisini söylemez."""
    monkeypatch.setattr(robots_drift, "REFRESH_AFTER", timedelta(days=10))

    assert "10 günden" in robots_drift.refresh(tmp_path / "hiç-yazılmaz.yaml", [], TODAY)
    assert "10 günden" in " ".join(robots_drift._parser().format_help().split())


def test_the_real_registry_changes_only_its_date_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gerçek `config/sources.yaml` + anlık görüntüler, canlısı aynı: her ölçülen kaynağın tarih
    satırı bugüne döner, başka HİÇBİR bayt değişmez, dosya aynı kayıtlara ayrışır; dosya izni ve
    `config/` içeriği (geçici dosya kalmadan) aynı kalır."""
    shutil.copytree(REPO / "config", tmp_path / "config")
    monkeypatch.chdir(tmp_path)
    sources = load_sources(REGISTRY)
    measured = [s for s in sources if (Path("config/robots") / f"{s.id}.txt").is_file()]
    today = max(s.robots_verified_at for s in measured) + timedelta(days=8)
    live: dict[str, Live] = {
        str(urlsplit(s.base_url).hostname): _same(
            (Path("config/robots") / f"{s.id}.txt").read_text(encoding="utf-8")
        )
        for s in measured
    }
    before = REGISTRY.read_bytes()
    mode = stat.S_IMODE(REGISTRY.stat().st_mode)
    listing = sorted(path.name for path in Path("config").iterdir())

    code = robots_drift.main(
        ["--refresh"], transport=_serve(live), now=datetime.combine(today, time(12), tzinfo=UTC)
    )

    assert code == 0
    assert stat.S_IMODE(REGISTRY.stat().st_mode) == mode, "dosya izni değişti"
    assert sorted(path.name for path in Path("config").iterdir()) == listing
    changed = [
        (old, new)
        for old, new in zip(
            before.splitlines(keepends=True),
            REGISTRY.read_bytes().splitlines(keepends=True),
            strict=True,
        )
        if old != new
    ]
    assert len(changed) == len(measured), changed
    for old, new in changed:
        assert re.fullmatch(rb"    robots_verified_at: \d{4}-\d{2}-\d{2}\n", old), old
        assert new == f"    robots_verified_at: {today}\n".encode()
    refreshed = {s.id for s in measured}
    assert load_sources(REGISTRY) == tuple(
        dataclasses.replace(s, robots_verified_at=today) if s.id in refreshed else s
        for s in sources
    )
