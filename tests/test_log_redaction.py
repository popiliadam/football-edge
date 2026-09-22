"""Pipeline'ın hiçbir credential'ı log satırına düşmemeli (K1).

Depo PUBLIC: Actions logları herkese açık. Odds API anahtarı `apiKey` sorgu parametresinde,
DSN ve parolası psycopg/pooler hatalarında görünebilir. GitHub'ın tam eşleşme maskelemesi tek
savunma hattı olmasın diye değerler hem `redact`te hem kök handler'ın formatter'ında
ayıklanır; httpx'in istek satırı hiç üretilmez.
"""

from __future__ import annotations

import io
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import pytest

from football_edge import collect, fetch
from football_edge.redaction import redact
from tests.fake_db import FakeLedgerDb

FAKE_KEY = "sahte-odds-anahtari"
KEYED_URL = f"https://api.the-odds-api.com/v4/sports/soccer_bad/odds?apiKey={FAKE_KEY}&regions=eu"
FAKE_TYPESAFE = "sahte-typesafe-anahtari"
FAKE_DB_PASSWORD = "sahte-parola"
FAKE_DSN = f"postgresql://sahte_kullanici:{FAKE_DB_PASSWORD}@db.sahte.invalid:5432/postgres"
PIPELINE_ENV: dict[str, str | None] = {
    "ODDS_API_KEY": FAKE_KEY,
    "TYPESAFE_API_KEY": FAKE_TYPESAFE,
    "DATABASE_URL": FAKE_DSN,
}
QUIET = ("httpx", "httpcore")
LOGGER = logging.getLogger(__name__)

LEAGUES_YAML = """
leagues:
  - id: bad.1
    odds_api_key: soccer_bad
    name: Bad
    country: X
    lang: en
    gl: GB
    active: true
    footystats_path: /bad/xg
"""


# ── redact ──────────────────────────────────────────────────────────────────


def test_redact_masks_a_plain_secret() -> None:
    assert redact(f"anahtar {FAKE_KEY} sızdı", [FAKE_KEY]) == "anahtar *** sızdı"


def test_redact_masks_a_secret_with_a_trailing_newline_both_as_is_and_stripped() -> None:
    # Panele yapıştırılan secret'ın sonunda `\n` kalabilir; metne çoğu kez kırpılmış hâli düşer.
    assert redact(f"anahtar {FAKE_KEY} sızdı", [f"{FAKE_KEY}\n"]) == "anahtar *** sızdı"
    assert redact(f"önce {FAKE_KEY}\nsonra", [f"{FAKE_KEY}\n"]) == "önce ***sonra"


@pytest.mark.parametrize("name", ["apiKey", "APIKEY", "apikey"])
def test_redact_masks_the_apikey_parameter_in_any_case(name: str) -> None:
    assert redact(f"odds?{name}=abc123&regions=eu", []) == f"odds?{name}=***&regions=eu"


def test_redact_masks_a_percent_encoded_apikey_value() -> None:
    # Sonunda `\n` olan anahtarı httpx URL'ye `%0A` diye kodlar; düz eşleşme onu kaçırır.
    assert redact("odds?apiKey=abc123%0A&regions=eu", []) == "odds?apiKey=***&regions=eu"


@pytest.mark.parametrize("end", ["&regions=eu", " sonra", "'", '"', "\nsonraki satır", ""])
def test_redact_ends_the_apikey_value_at_its_delimiter(end: str) -> None:
    assert redact(f"odds?apiKey=abc123{end}", []) == f"odds?apiKey=***{end}"


@pytest.mark.parametrize("secret", ["", "\n"])
def test_redact_ignores_an_empty_secret(secret: str) -> None:
    # Boş secret'la `replace` her karakterin arasına `***` sokar; yalnız `\n` her satırı ezer.
    text = "hiçbir şey\ngizlenmez"
    assert redact(text, [secret]) == text


# ── configure_logging ───────────────────────────────────────────────────────


@contextmanager
def _bare_root_logger() -> Iterator[None]:
    """Kökü pytest'in handler'larından arındırır; çıkışta hepsini geri koyar.

    pytest çağrı evresinde köke kendi handler'larını takar: o hâlde `basicConfig` no-op olur
    ve test üretimdeki kurulumu hiç görmez. httpx seviyeleri de sıfırlanır — `collect.main()`i
    çağıran başka bir test onları WARNING'de bırakmış olabilir, mutasyon o sızıntıyla gizlenir.
    """
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_levels = {name: logging.getLogger(name).level for name in ("", *QUIET)}
    for handler in saved_handlers:
        root.removeHandler(handler)
    for name in QUIET:
        logging.getLogger(name).setLevel(logging.NOTSET)
    try:
        yield
    finally:
        for handler in root.handlers[:]:
            root.removeHandler(handler)
            handler.close()
        for handler in saved_handlers:
            root.addHandler(handler)
        for name, level in saved_levels.items():
            logging.getLogger(name).setLevel(level)


def _status_error() -> httpx.HTTPStatusError:
    with pytest.raises(httpx.HTTPStatusError) as caught:
        httpx.Response(500, request=httpx.Request("GET", KEYED_URL)).raise_for_status()
    return caught.value


def test_logged_status_error_traceback_hides_the_key_but_keeps_the_error_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ODDS_API_KEY", FAKE_KEY)
    error = _status_error()
    assert FAKE_KEY in str(error), "ön koşul: httpx hata mesajı tam URL'yi taşımalı"
    stream = io.StringIO()

    with _bare_root_logger():
        collect.configure_logging(stream)
        LOGGER.exception("lig=%s toplanamadı", "bad.1", exc_info=error)

    out = stream.getvalue()
    assert FAKE_KEY not in out, out
    assert "HTTPStatusError" in out, f"traceback yutuldu: {out!r}"
    assert "ERROR lig=bad.1 toplanamadı" in out, f"log biçimi değişmemeli: {out!r}"


def _logged(monkeypatch: pytest.MonkeyPatch, env: dict[str, str | None], value: str) -> str:
    """Ortamı kurar (`None` = tanımsız), kurulumdan tek bir WARNING satırı geçirir."""
    for name, secret in env.items():
        if secret is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, secret)
    stream = io.StringIO()
    with _bare_root_logger():
        collect.configure_logging(stream)
        LOGGER.warning("değer: %s", value)
    return stream.getvalue()


@pytest.mark.parametrize(
    "value",
    [FAKE_KEY, FAKE_TYPESAFE, FAKE_DSN, FAKE_DB_PASSWORD],
    ids=["odds-anahtari", "typesafe-anahtari", "dsn-tamami", "dsn-parolasi"],
)
def test_every_pipeline_credential_is_masked_in_a_log_line(
    value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # `apikey=` regex'i bunları yakalamaz: liste ortamdan gelmeli. Satırın TAMAMI kıyaslanır —
    # DSN'nin yalnız parolası gizlenseydi kullanıcı ve host açıkta kalırdı.
    out = _logged(monkeypatch, PIPELINE_ENV, value)
    assert out.endswith("WARNING değer: ***\n"), out


@pytest.mark.parametrize("form", ["p%40ss-sahte", "p@ss-sahte"], ids=["url-kodlu", "cozulmus"])
def test_a_percent_encoded_dsn_password_is_masked_in_both_forms(
    form: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # DSN'de parola yüzde-kodlu durur; psycopg/pooler hatası onu çözülmüş hâliyle de basabilir.
    dsn = "postgresql://sahte_kullanici:p%40ss-sahte@db.sahte.invalid:5432/postgres"
    out = _logged(monkeypatch, {"DATABASE_URL": dsn}, form)
    assert out.endswith("WARNING değer: ***\n"), out


def test_a_missing_dsn_does_not_break_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    out = _logged(monkeypatch, {"DATABASE_URL": None, "ODDS_API_KEY": FAKE_KEY}, FAKE_KEY)
    assert out.endswith("WARNING değer: ***\n"), out


def test_an_unparsable_dsn_does_not_break_logging_and_is_still_masked_whole(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dsn = "postgresql://sahte_kullanici:bozuk-parola@[sahte/postgres"
    with pytest.raises(ValueError):
        urlsplit(dsn)  # ön koşul: bu DSN gerçekten ayrıştırılamıyor
    out = _logged(monkeypatch, {"DATABASE_URL": dsn}, dsn)
    assert out.endswith("WARNING değer: ***\n"), out


def test_configure_logging_keeps_root_at_info_and_raises_httpx_to_warning() -> None:
    with _bare_root_logger():
        collect.configure_logging(io.StringIO())
        root_level = logging.getLogger().level
        levels = {name: logging.getLogger(name).level for name in QUIET}

    assert root_level == logging.INFO, "kök seviyesi değişmemeli"
    assert all(level >= logging.WARNING for level in levels.values()), levels


def test_httpx_request_line_is_not_emitted_even_at_debug(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ODDS_API_KEY", FAKE_KEY)
    stream = io.StringIO()
    transport = httpx.MockTransport(lambda request: httpx.Response(200))

    with _bare_root_logger():
        collect.configure_logging(stream)
        logging.getLogger().setLevel(logging.DEBUG)
        LOGGER.debug("kontrol: DEBUG açık")
        with httpx.Client(transport=transport) as client:
            client.get(KEYED_URL)

    out = stream.getvalue()
    assert "kontrol: DEBUG açık" in out, "kök DEBUG'a inmedi — test hiçbir şey ölçmüyor"
    assert "HTTP Request" not in out, out


# ── gerçek yol: main() → rounds / results → LOGGER.exception ────────────────


@pytest.mark.parametrize("command", ["snapshot", "fetch-results"])
def test_main_keeps_the_key_out_of_a_failing_league_traceback(
    command: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`rounds._collect` ve `results.collect_results` 500'ü `LOGGER.exception`la basar;
    `main()`in kurduğu kök handler (stderr) anahtarı taşımamalı."""
    leagues_path = tmp_path / "leagues.yaml"
    leagues_path.write_text(LEAGUES_YAML, encoding="utf-8")
    monkeypatch.setattr(collect, "LEAGUES_PATH", leagues_path)
    monkeypatch.setattr(fetch, "LEAGUES_PATH", leagues_path)
    monkeypatch.setattr(collect, "connect", lambda: FakeLedgerDb())
    real_client = httpx.Client
    transport = httpx.MockTransport(lambda request: httpx.Response(500, json={"message": "boom"}))
    monkeypatch.setattr(collect.httpx, "Client", lambda: real_client(transport=transport))
    monkeypatch.setenv("ODDS_API_KEY", FAKE_KEY)

    with _bare_root_logger():
        code = collect.main([command])

    err = capsys.readouterr().err
    assert code == collect.EXIT_LEAGUE_FAILED
    assert "HTTPStatusError" in err, f"traceback kök handler'a ulaşmadı: {err!r}"
    assert FAKE_KEY not in err, err
