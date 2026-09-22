"""Log çıktısından pipeline'ın credential'larını ayıklar (K1).

Depo PUBLIC: Actions logları herkese açık. GitHub'ın secret maskelemesi yalnız TAM eşleşmeyi
gizler; bu modül ikinci savunma hattıdır. Odds API anahtarı yalnız `apiKey` sorgu
parametresinde taşınır.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from urllib.parse import unquote, urlsplit

REDACTED = "***"

# Değer `&`, boşluk, tırnak ya da satır sonunda biter; yüzde-kodlu değer (`%0A`) de dâhil.
_API_KEY_PARAM = re.compile(r"(apikey=)[^&\s'\"]+", re.IGNORECASE)


def redact(text: str, secrets: Iterable[str]) -> str:
    """Her secret'ı olduğu gibi ve kırpılmış hâliyle, her `apikey=` değerini `***` yapar."""
    redacted = text
    for secret in secrets:
        if not secret.strip():
            continue  # boş secret'la `replace` her karakterin arasına `***` sokar
        redacted = redacted.replace(secret, REDACTED).replace(secret.strip(), REDACTED)
    return _API_KEY_PARAM.sub(lambda match: match.group(1) + REDACTED, redacted)


def dsn_password_forms(dsn: str) -> tuple[str, ...]:
    """DSN parolasının URL'deki (yüzde-kodlu) ve çözülmüş hâli; parola yoksa boş.

    psycopg/pooler hataları DSN parçalarını, parolayı çözülmüş hâliyle de basabilir.
    """
    try:
        password = urlsplit(dsn).password
    except ValueError:
        return ()  # ayrıştırılamayan DSN log kurulumunu düşürmemeli; tam hâli yine listede
    if not password:
        return ()
    return (password, unquote(password))
