"""Odds API anahtarı hiçbir log satırına düşmemeli (K1).

Depo PUBLIC: Actions logları herkese açık ve anahtar yalnız `apiKey` sorgu parametresinde
taşınır. GitHub'ın tam eşleşme maskelemesi tek savunma hattı olmasın diye anahtar hem
`redact`te hem kök handler'ın formatter'ında ayıklanır; httpx'in istek satırı hiç üretilmez.
"""

from __future__ import annotations

import io
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest

from football_edge import collect, fetch
from football_edge.redaction import redact
from tests.fake_db import FakeLedgerDb

FAKE_KEY = "sahte-odds-anahtari"
KEYED_URL = f"https://api.the-odds-api.com/v4/sports/soccer_bad/odds?apiKey={FAKE_KEY}&regions=eu"
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


def test_the_env_key_is_masked_even_outside_the_apikey_parameter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # `apikey=` regex'i tek başına bunu yakalamaz: secret listesi ortamdan gelmeli.
    monkeypatch.setenv("ODDS_API_KEY", FAKE_KEY)
    stream = io.StringIO()

    with _bare_root_logger():
        collect.configure_logging(stream)
        LOGGER.warning("yanıt gövdesi anahtarı yansıttı: %s", FAKE_KEY)

    out = stream.getvalue()
    assert FAKE_KEY not in out, out
    assert "yanıt gövdesi anahtarı yansıttı: ***" in out, out


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
