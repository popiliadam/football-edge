"""Zaman semantiği (tasarım §4.5, D4, D5): sızıntının tamamı buradaki iki kurala bağlıdır.

Kapanış öncesi oranlar hafta sonu maçları için cuma, hafta içi maçları için salı öğleden sonra
toplanır (`notes.txt`); karar anı o öğleden sonranın EN ERKEN anıdır, 12:00 Europe/London. Sonuç
başlamadan 3 saat sonra, saat yoksa ertesi gün 03:00 Europe/London bilinir (tutucu kural).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")
DECISION_HOUR = 12
RESULT_LAG = timedelta(hours=3)
_RESULT_HOUR_WITHOUT_KICKOFF = 3
_TUESDAY = 1
_FRIDAY = 4
_MIDWEEK = frozenset({1, 2, 3})  # salı, çarşamba, perşembe


def _decision_day(match_date: date) -> date:
    """Cuma–pazartesi maçı: o gün ya da önceki son cuma; salı–perşembe maçı: son salı."""
    weekday = match_date.weekday()
    back = weekday - _TUESDAY if weekday in _MIDWEEK else (weekday - _FRIDAY) % 7
    return match_date - timedelta(days=back)


def _london(day: date, hour: int) -> datetime:
    # Ofset o GÜNÜN kuralından gelir: yaz saati geçişi karar günüyle maç günü arasına düşebilir.
    return datetime.combine(day, time(hour), tzinfo=LONDON).astimezone(UTC)


def _aware(kickoff: datetime) -> datetime:
    # Saat dilimsiz başlama sessizce yerel saat sayılırdı; HistMatch.kickoff UTC taşır.
    if kickoff.utcoffset() is None:
        raise ValueError(f"başlama anı saat dilimsiz: {kickoff.isoformat()}")
    return kickoff


def decision_at(match_date: date, kickoff: datetime | None) -> datetime | None:
    """Karar anı (UTC). Başlama biliniyor ve karar ondan önce değilse None: maçın kararı yok."""
    instant = _london(_decision_day(match_date), DECISION_HOUR)
    if kickoff is not None and instant >= _aware(kickoff):
        return None
    return instant


def result_known_at(match_date: date, kickoff: datetime | None) -> datetime:
    """Sonucun (ve maç istatistiğinin) bilindiği an (UTC)."""
    if kickoff is not None:
        return (_aware(kickoff) + RESULT_LAG).astimezone(UTC)
    return _london(match_date + timedelta(days=1), _RESULT_HOUR_WITHOUT_KICKOFF)
