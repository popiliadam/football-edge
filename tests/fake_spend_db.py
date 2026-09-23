"""`jev_spend` bağlantısı taklidi: `PostgresSpendLedger`in İKİ sorgusunu tanır, başkasını reddeder.

Ay toplamı yazılan satırları da sayar: tavan kontrolü aynı koşuda yazılanı görmezse ikinci çağrı
tavanı delerdi. `connect()`in yerine geçtiği için `with` biçimini ve `autocommit`i taşır.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass
class FakeSpendConn:
    autocommit: bool = False
    total: Decimal = Decimal("0")
    inserted: list[tuple[Any, ...]] = field(default_factory=list)

    def cursor(self) -> _Cursor:
        return _Cursor(self)

    def __enter__(self) -> FakeSpendConn:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    @property
    def kinds(self) -> list[str]:
        return [row[1] for row in self.inserted]


class _Cursor:
    def __init__(self, conn: FakeSpendConn) -> None:
        self._conn = conn
        self._result: tuple[Any, ...] | None = None

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        text = " ".join(sql.split())
        if text.startswith("SELECT coalesce(sum(cost_usd), 0) FROM jev_spend"):
            spent = sum((Decimal(str(row[2])) for row in self._conn.inserted), Decimal("0"))
            self._result = (self._conn.total + spent,)
        elif text.startswith("INSERT INTO jev_spend"):
            self._conn.inserted = [*self._conn.inserted, params]
        else:
            raise AssertionError(f"taklit bu sorguyu tanımıyor: {text}")

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._result
