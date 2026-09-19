from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any

import psycopg

from football_edge.jev import NO_MATCH, ChoiceAnswer, JevClient
from football_edge.naming import normalise_team
from football_edge.observations import latest_observations

LOGGER = logging.getLogger("football_edge.mapping")

_INSTRUCTIONS = (
    "The alias below is a football club name taken from one data source. "
    "Select the club from the canonical list that refers to the SAME club. "
    "Clubs from the same city can be different clubs, and a club may field teams in other "
    "sports — only an exact same-club match counts. "
    f"If no option refers to the same club, select '{NO_MATCH}'."
)


@dataclass(frozen=True)
class Resolution:
    alias: str
    canonical_id: str | None
    confidence: float
    reason: str


def candidates(alias: str, canonical: tuple[str, ...], *, limit: int = 8) -> tuple[str, ...]:
    """Normalize edilmiş ad benzerliğine göre en olası adaylar.

    Model, listeye KONULMAYAN bir değeri seçemez (TypeSafe Choice dokümanı: "the model
    cannot choose an omitted value"), o yüzden `limit` cömert tutulur. Aday üretimi
    deterministiktir ve testi vardır — daraltmayı modele bırakmak, hatayı görünmez yapar.
    """
    target = normalise_team(alias)
    scored = sorted(
        canonical,
        key=lambda name: SequenceMatcher(None, target, normalise_team(name)).ratio(),
        reverse=True,
    )
    return tuple(scored[:limit])


def resolve(
    alias: str,
    canonical: tuple[str, ...],
    client: JevClient,
    *,
    league: str,
    threshold: float = 0.75,
) -> Resolution:
    """Takma adı kanonik ada eşler; EŞİK ALTINDAKİ eşleşme reddedilir.

    Reddetmek sessiz kalmak değildir: `Resolution.reason` sebebi taşır ve çağıran onu
    raporlar. Yanlış bir eşleşme hiçbir zaman kırmızı vermez; eksik bir eşleşme raporda
    görünür ve elle kapatılabilir.
    """
    normalised = normalise_team(alias)
    for name in canonical:
        if normalise_team(name) == normalised:
            # Deterministik cevabı modele sormak hem para hem gürültüdür (spec §5.2:
            # "bunun cevabı tabloda zaten var mı?").
            return Resolution(alias, name, 1.0, "birebir normalize eşleşme")

    options = candidates(alias, canonical)
    criteria = {name: f"The club known as {name}" for name in options}
    criteria[NO_MATCH] = "None of the listed clubs is the same club as the alias"
    answer: ChoiceAnswer = client.ask_choice(
        state={"alias": alias, "league": league, "source_naming": normalised},
        instructions=_INSTRUCTIONS,
        criteria=criteria,
    )
    if answer.choice == NO_MATCH:
        return Resolution(alias, None, answer.confidence, "model 'hiçbiri' dedi")
    if answer.confidence < threshold:
        return Resolution(
            alias,
            None,
            answer.confidence,
            f"güven {answer.confidence:.2f} < eşik {threshold:.2f} — yazılmadı",
        )
    return Resolution(alias, answer.choice, answer.confidence, "model seçti")


def canonical_team_names(conn: psycopg.Connection[Any], league_id: str) -> tuple[str, ...]:
    """`matches` tablosundaki KANONİK (The Odds API) takım adları — TEK ligle sınırlı.

    `matches.id` zaten The Odds API'den geliyor (spec §5.3) — bu yüzden `home_team`/
    `away_team` başka bir kaynağa değil, doğrudan API'nin kendi yazımına aittir; ayrı
    bir "kanonik ad" tablosu gerekmez. Lig SINIRLANMADAN sorgulanmaz: aynı ad farklı
    ligde farklı kulüp olabilir (bkz. `resolve` docstring'i) — çağıran her zaman TEK
    bir `league_id` verir, tüm defteri değil.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT home_team FROM matches WHERE league_id = %s "
            "UNION SELECT away_team FROM matches WHERE league_id = %s",
            (league_id, league_id),
        )
        names = {str(row[0]) for row in cur.fetchall()}
    return tuple(sorted(names))


def write_aliases(
    conn: psycopg.Connection[Any],
    source_id: str,
    entity_kind: str,
    resolutions: tuple[Resolution, ...],
    now: datetime,
) -> int:
    """YALNIZ çözülmüş eşleşmeleri yazar. Çözülmeyenler çağıran tarafından raporlanır."""
    rows = [entry for entry in resolutions if entry.canonical_id is not None]
    if not rows:
        return 0
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO entity_aliases
              (source_id, entity_kind, alias, canonical_id, confidence, decided_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_id, entity_kind, alias) DO UPDATE SET
              canonical_id = excluded.canonical_id,
              confidence = excluded.confidence,
              decided_at = excluded.decided_at
            """,
            [
                (source_id, entity_kind, entry.alias, entry.canonical_id, entry.confidence, now)
                for entry in rows
            ],
        )
    conn.commit()
    return len(rows)


def _alias_text(payload: dict[str, Any], source_id: str) -> str:
    """Takma adın GÖRÜNÜR metnini gözlem payload'ından çıkarır.

    `"team_name"` footystats'ın kendi sözleşmesi (bkz. collectors/footystats.py — bugün
    `entity_kind="team"` yayınlayan TEK kaynak, TFF şimdilik yalnız `fixture_official`
    gözlemliyor). Alan yoksa SESSİZCE atlamak yerine adıyla patlar: aksi hâlde henüz
    `map-entities`e bağlanmamış bir kaynağı denemek "0 eşleşme, her şey yolunda" gibi
    görünürdü — below-threshold'un bile raporlanması gerektiği ilkesiyle aynı ruh.
    """
    text = payload.get("team_name")
    if not isinstance(text, str) or not text:
        raise RuntimeError(
            f"{source_id}: gözlem payload'ında 'team_name' yok — bu kaynak henüz "
            "map-entities'e bağlanmadı"
        )
    return text


@dataclass(frozen=True)
class MappingReport:
    written: int
    # TÜMÜ — çözülen VE çözülmeyen. Çağıran unresolved'ı adıyla raporlar (spec §5.3):
    # atlanan bir eşleşme, farklı kılıktaki sessiz join hatasıdır.
    resolutions: tuple[Resolution, ...]


def resolve_source_aliases(
    conn: psycopg.Connection[Any],
    client: JevClient,
    source_id: str,
    league_id: str,
    canonical: tuple[str, ...],
    now: datetime,
    *,
    entity_kind: str = "team",
    threshold: float = 0.75,
) -> MappingReport | None:
    """Bir kaynağın BİR ligdeki güncel takım gözlemlerini kanonik listeye eşler ve
    YALNIZ çözülenleri yazar. Bu ligde hiç gözlem yoksa (`entity_key` `{league_id}:`
    öneki taşımıyorsa) `None` döner — çağıran bunu "gözlem yok" diye ayrı raporlar.

    `canonical` PARAMETREDİR, burada sorgulanmaz: boş kanonik liste ile hiç Jev
    kurulmadan/gözlem okunmadan erken dönmek çağıranın işi (bkz. `collect.py:
    _map_entities_command`) — bu fonksiyon yalnız "kanonik VAR, şimdi eşle" adımıdır.
    """
    prefix = f"{league_id}:"
    aliases = tuple(
        _alias_text(entry.payload, source_id)
        for entry in latest_observations(conn, source_id, entity_kind)
        if entry.entity_key.startswith(prefix)
    )
    if not aliases:
        return None
    resolutions = tuple(
        resolve(alias, canonical, client, league=league_id, threshold=threshold)
        for alias in aliases
    )
    written = write_aliases(conn, source_id, entity_kind, resolutions, now)
    return MappingReport(written=written, resolutions=resolutions)
