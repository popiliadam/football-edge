"""Ön kaydın depoyla karşılaştırılması (Plan 3 spec §4, §5).

İki denetim. `seal_violations` KALICIDIR, her push'ta koşar: donmuş dosyalar mühürle birebir, küme
sürümü, bileşiğin `tier2`yi tam bölmesi, D8 listesi, `LEVEL_SCORES` ve dil giriş eşikleri koddaki
karşılıklarıyla aynı, D5 ligleri bilinen lig, mühürlü diller hâlâ üretimde. Donmuş bir dosya
değişirse kapı kırmızı kalır — bilinçli: spec §5'in kapanış kaydı yazılmadan pencere sessizce
sürmesin. `seal_time_violations` MÜHÜR ANINDADIR: kollar dâhil her dosya birebir, D5 aktif liglere,
mühürlü diller üretim dillerine EŞİT; mühür commit'inden önce boş dönmelidir. Sonra kolların
değişmesi serbesttir (spec §5); rapor aynı fonksiyonla farkı adıyla basar. CI derinliği 1 ve
etiketsiz klonladığı için hiçbiri git'e dayanmaz.
"""

from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

import yaml

from football_edge.calibration import production_ready
from football_edge.features.derive import LEVEL_SCORES
from football_edge.features.live_config import (
    LiveConfigError,
    live_prompt_version,
    load_live_config,
)
from football_edge.features.questions import QuestionsError, load_questions
from football_edge.gate4.preregistration import (
    FROZEN_FILES,
    LANGUAGES,
    LEAGUES,
    LIVE,
    OPS,
    QUESTIONS,
    RECORDED_FILES,
    Faz4Preregistration,
)
from football_edge.leagues import active_leagues, load_leagues


def _digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def _drift(prereg: Faz4Preregistration, root: Path, names: frozenset[str]) -> tuple[str, ...]:
    found: tuple[str, ...] = ()
    for name in sorted(names):
        digest = _digest(root / name)
        if digest is None:
            found = (*found, f"{name}: mühürlü dosya yok")
        elif digest != prereg.sha256[name]:
            found = (*found, f"{name}: baytlar mühürdekiyle aynı değil")
    return found


def _question_violations(prereg: Faz4Preregistration, root: Path) -> tuple[str, ...]:
    questions = load_questions(root / QUESTIONS)
    tier2 = {q.question_id for q in questions.tier2}
    composite = {*prereg.weakness, *prereg.strength, *prereg.excluded}
    found: tuple[str, ...] = ()
    if unknown := sorted(composite - tier2):
        found = (*found, f"feature: tier2'de olmayan soru {unknown}")
    if uncovered := sorted(tier2 - composite):
        found = (*found, f"feature: tier2'yi tam bölmüyor, dışarıda kalan {uncovered}")
    expected = {*composite, *(q.question_id for q in questions.tier3)}
    if set(prereg.d8_questions) != expected:
        found = (*found, f"d8_questions: bileşik + excluded + tier3 ({len(expected)} id) olmalı")
    return found


def _production_codes(root: Path) -> frozenset[str]:
    """`production_enabled: true` dillerin kodları; biçim bozuksa `ValueError` (adıyla)."""
    raw = yaml.safe_load((root / LANGUAGES).read_text(encoding="utf-8"))
    entries = raw.get("languages") if isinstance(raw, dict) else None
    if not isinstance(entries, list):
        raise ValueError(f"{LANGUAGES}: 'languages' listesi yok")
    codes: frozenset[str] = frozenset()
    for entry in entries:
        enabled = entry.get("production_enabled") if isinstance(entry, dict) else None
        if not isinstance(enabled, bool) or not isinstance(entry.get("code"), str):
            raise ValueError(f"{LANGUAGES}: code metin, production_enabled bool olmalı ({entry!r})")
        codes = codes | {entry["code"]} if enabled else codes
    return codes


def _leagues(root: Path, *, active: bool) -> frozenset[str] | str:
    """Lig kimlikleri (yalnız aktifler ya da hepsi); dosya yok/bozuksa adlı ihlal metni."""
    try:
        leagues = load_leagues(root / LEAGUES)
    except (ValueError, TypeError, KeyError, OSError) as error:
        return f"{LEAGUES}: okunamadı ({error})"
    return frozenset(league.id for league in (active_leagues(leagues) if active else leagues))


def _code_violations(prereg: Faz4Preregistration) -> tuple[str, ...]:
    found: tuple[str, ...] = ()
    if dict(prereg.level_scores) != dict(LEVEL_SCORES):
        found = (*found, "level_scores: features.derive.LEVEL_SCORES ile aynı değil (R190)")
    defaults = inspect.signature(production_ready).parameters
    if prereg.entry_min_n != defaults["min_n"].default:
        found = (*found, "languages.entry.min_n: calibration.production_ready eşiği değil (R182)")
    if prereg.entry_min_accuracy != defaults["min_accuracy"].default:
        found = (*found, "languages.entry.min_accuracy: production_ready eşiği değil (R182)")
    return found


def _config_violations(prereg: Faz4Preregistration, root: Path) -> tuple[str, ...]:
    found: tuple[str, ...] = ()
    version = live_prompt_version((root / QUESTIONS).read_bytes(), (root / LIVE).read_bytes())
    if prereg.tier2_prompt_version != version:
        found = (*found, "window.tier2_prompt_version: sha256(soru dosyası + faz4_live) değil")
    known = _leagues(root, active=False)
    if isinstance(known, str):
        found = (*found, known)
    elif unknown := sorted(set(prereg.d5_leagues) - known):
        found = (*found, f"d5_leagues: leagues.yaml'da olmayan lig {unknown}")
    try:
        if outside := sorted(set(prereg.sealed_languages) - _production_codes(root)):
            found = (*found, f"languages.sealed: üretimde olmayan dil {outside}")
    except (ValueError, OSError) as error:
        found = (*found, f"languages: {error}")
    try:
        model = load_live_config(
            root / LIVE, ops_path=root / OPS, questions_path=root / QUESTIONS
        ).jev_model
    except (LiveConfigError, OSError) as error:
        return (*found, f"{LIVE}: okunamadı ({error})")
    if prereg.entry_jev_model != model:
        found = (*found, "languages.entry.jev_model: faz4_live.yaml'ın jev_model'i olmalı")
    return found


def seal_violations(prereg: Faz4Preregistration, *, root: Path) -> tuple[str, ...]:
    """Kalıcı denetim: ön kaydın depoyla çeliştiği her nokta, adıyla; boş demet = mühür tutuyor."""
    found = _drift(prereg, root, FROZEN_FILES)
    if any(line.startswith((QUESTIONS, LIVE)) for line in found):
        return found  # soru ya da küme dosyası yoksa/değiştiyse kalan denetimler anlamsız
    try:
        questions = _question_violations(prereg, root)
    except QuestionsError as error:
        questions = (f"{QUESTIONS}: okunamadı ({error})",)
    return (*found, *questions, *_code_violations(prereg), *_config_violations(prereg, root))


def seal_time_violations(prereg: Faz4Preregistration, *, root: Path) -> tuple[str, ...]:
    """Mühür anı: donmuş + kollar her dosya birebir, D5 = aktif ligler, mühürlü diller = üretim.
    Mühür commit'inin KENDİSİNDE (origin/main birleştirmesinden sonra) boş dönmelidir."""
    found = _drift(prereg, root, FROZEN_FILES | RECORDED_FILES)
    active = _leagues(root, active=True)
    if isinstance(active, str):
        found = (*found, active)
    elif set(prereg.d5_leagues) != active:
        found = (*found, f"d5_leagues: aktif ligler {sorted(active)} olmalı")
    try:
        production = _production_codes(root)
    except (ValueError, OSError) as error:
        return (*found, f"languages: {error}")
    if set(prereg.sealed_languages) != production:
        found = (*found, f"languages.sealed: üretim dilleri {sorted(production)} olmalı")
    return found
