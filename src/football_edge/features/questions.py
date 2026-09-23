"""Jev soru bataryası: `config/jev_questions.yaml` (spec §5.2 tablosu; R164).

`prompt_version` dosyanın sha256'sıdır: tek harf değişen soru yeni bir sürümdür ve eski cevaplarla
karışmaz. Kademe 1'in iki sorusunun seçenekleri haberden kurulur (maç adayları, önceki haberler);
dosyada seçenekleri YOKTUR, yükleyici yalnız her zaman listede olan seçeneği koyar (`ALWAYS`).
Kademe 2–4 soruları TARAF başına sorulur (`{team}`) ve ortak dört düzeyli ölçekle cevaplanır:
özellik `f = ev − deplasman` iki tarafın aynı sorusundan kurulur.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

from football_edge.features.types import AWAY, HOME
from football_edge.jev import NO_MATCH, Question

QUESTIONS_PATH = Path("config/jev_questions.yaml")

MATCH_QUESTION = "t1_mac_taraf"
CLUSTER_QUESTION = "t1_kume"
RELIABILITY_QUESTION = "t1_guvenilirlik"
CONFLICT_QUESTION = "t1_celiski"
NEW_EVENT = "new event"
# Seçenekleri haberden kurulan sorularda her zaman listede duran seçenek: model "hiçbiri"ni
# seçebilmeli, yoksa her haberi bir maça ya da bir kümeye zorla bağlar.
ALWAYS: Mapping[str, Mapping[str, str]] = MappingProxyType(
    {
        MATCH_QUESTION: MappingProxyType(
            {NO_MATCH: "The news is not relevant to any listed fixture"}
        ),
        CLUSTER_QUESTION: MappingProxyType(
            {NEW_EVENT: "An event none of the earlier items reported"}
        ),
    }
)
DYNAMIC_QUESTIONS = frozenset(ALWAYS)
TIER1_QUESTIONS = frozenset({*DYNAMIC_QUESTIONS, RELIABILITY_QUESTION, CONFLICT_QUESTION})
# Güvenilirlik = bu iki seçeneğin olasılık toplamı (`tier1.gates_from`).
RELIABLE_CHOICES = ("official", "reported")

TEAM_SLOT = "{team}"
LEVEL_CRITERIA: Mapping[str, str] = MappingProxyType(
    {
        "none": "The news says nothing about this for the team, or says it does not apply",
        "low": "The news suggests this applies to the team only slightly",
        "medium": "The news suggests this clearly applies to the team",
        "high": "The news suggests this applies to the team strongly",
    }
)
TIERS = ("tier1", "tier2", "tier3", "tier4")
_ID = re.compile(r"^t([1-4])_[a-z0-9_]+$")
_ENTRY_KEYS = frozenset({"id", "instructions", "criteria"})


class QuestionsError(ValueError):
    """Soru dosyası sözleşmeye uymuyor; eksik/fazla alan ya da yinelenen soru."""


@dataclass(frozen=True)
class QuestionSet:
    prompt_version: str
    tier1: tuple[Question, ...]
    tier2: tuple[Question, ...]
    tier3: tuple[Question, ...]
    tier4: tuple[Question, ...]


def _criteria(entry: Mapping[str, Any], question_id: str) -> Mapping[str, str]:
    raw = entry.get("criteria")
    if not isinstance(raw, Mapping) or not raw:
        raise QuestionsError(f"{question_id}: seçenekler (criteria) eksik")
    if not all(isinstance(k, str) and isinstance(v, str) and v for k, v in raw.items()):
        raise QuestionsError(f"{question_id}: seçenekler metin → metin olmalı")
    return MappingProxyType(dict(raw))


def _tier1(entry: Mapping[str, Any], question_id: str, instructions: str) -> Question:
    if question_id in DYNAMIC_QUESTIONS:
        if "criteria" in entry:
            raise QuestionsError(f"{question_id}: seçenekleri haberden kurulur, dosyada olamaz")
        return Question(question_id, instructions, ALWAYS[question_id])
    criteria = _criteria(entry, question_id)
    if question_id == RELIABILITY_QUESTION and not set(RELIABLE_CHOICES) <= set(criteria):
        raise QuestionsError(f"{question_id}: {RELIABLE_CHOICES} seçenekleri zorunlu")
    return Question(question_id, instructions, criteria)


def _side_question(entry: Mapping[str, Any], question_id: str, instructions: str) -> Question:
    if "criteria" in entry:
        raise QuestionsError(f"{question_id}: kademe 2–4 ortak ölçekle cevaplanır, seçenek olamaz")
    if instructions.count(TEAM_SLOT) != 1 or instructions.count("{") != 1:
        raise QuestionsError(f"{question_id}: talimat tek bir {TEAM_SLOT} yuvası taşımalı")
    return Question(question_id, instructions, LEVEL_CRITERIA)


def _question(entry: object, tier: int) -> Question:
    if not isinstance(entry, Mapping) or not set(entry) <= _ENTRY_KEYS:
        raise QuestionsError(f"tier{tier}: soru alanları {sorted(_ENTRY_KEYS)} dışında: {entry}")
    question_id, instructions = entry.get("id"), entry.get("instructions")
    if not isinstance(question_id, str) or (found := _ID.match(question_id)) is None:
        raise QuestionsError(f"tier{tier}: geçersiz soru kimliği {question_id!r}")
    if int(found.group(1)) != tier:
        raise QuestionsError(f"{question_id}: kimliğin öneki kademesiyle ({tier}) uyuşmuyor")
    if not isinstance(instructions, str) or not instructions.strip():
        raise QuestionsError(f"{question_id}: talimat boş")
    if tier == 1:
        return _tier1(entry, question_id, instructions.strip())
    return _side_question(entry, question_id, instructions.strip())


def load_questions(path: Path) -> QuestionSet:
    content = path.read_bytes()
    raw = yaml.safe_load(content)
    if not isinstance(raw, Mapping) or set(raw) != set(TIERS):
        raise QuestionsError(f"{path}: üst düzey alanlar tam olarak {list(TIERS)} olmalı")
    tiers = tuple(
        tuple(_question(entry, number) for entry in (raw[name] or ()))
        for number, name in enumerate(TIERS, start=1)
    )
    questions = tuple(question for tier in tiers for question in tier)
    ids = [question.question_id for question in questions]
    if len(set(ids)) != len(ids):
        raise QuestionsError(f"{path}: yinelenen soru kimliği")
    texts = [question.instructions for question in questions]
    if len(set(texts)) != len(texts):
        raise QuestionsError(f"{path}: aynı talimat iki kez soruluyor")
    if {question.question_id for question in tiers[0]} != TIER1_QUESTIONS:
        raise QuestionsError(f"{path}: kademe 1 tam olarak {sorted(TIER1_QUESTIONS)} olmalı")
    return QuestionSet(
        prompt_version=hashlib.sha256(content).hexdigest(),
        tier1=tiers[0],
        tier2=tiers[1],
        tier3=tiers[2],
        tier4=tiers[3],
    )


def for_team(question: Question, *, side: str, team: str) -> Question:
    """Kademe 2–4 sorusunu bir tarafa bağlar: kimlik `<soru>:<taraf>`, yuva takım adıyla dolar."""
    if side not in (HOME, AWAY):
        raise ValueError(f"taraf {HOME!r} ya da {AWAY!r} olmalı: {side!r}")
    if TEAM_SLOT not in question.instructions:
        raise ValueError(f"{question.question_id}: taraf sorusu değil")
    return Question(
        f"{question.question_id}:{side}",
        question.instructions.replace(TEAM_SLOT, team),
        question.criteria,
    )
