"""Her Jev çağrı yolu tavandan ve `jev_spend` defterinden geçer (spec §9, R159; son inceleme I-1).

`map-entities` ve `calibrate` `TypeSafeJev`i çıplak çağırıyordu: faturalanan çağrı defterde yoktu,
sonraki `tier1` ay toplamını eksik okuyordu ve $25 tavanı o kadar yumuşaktı. İki katman sınanır:
her komutun davranışı (çağrı başına bir defter satırı, tavanda adıyla çıkış, anahtarsız komut
bağlanmadan çıkar) ve kaynak kuralı (yeni bir çağrı yeri sarmalayıcıyı atlarsa kırmızı).
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from football_edge import collect
from football_edge.jev import EXIT_NO_JEV_KEY, ChoiceAnswer
from football_edge.jev_budget import EXIT_BUDGET, KIND_CHOICE, MONTHLY_CAP_USD
from football_edge.mapping import MappingReport
from tests.fake_jev import FakeJev
from tests.fake_spend_db import FakeSpendConn

SRC = Path(__file__).resolve().parent.parent / "src" / "football_edge"
# Sarmalayıcının kendisi ve sarılan istemci: kural bu ikisinin DIŞINDAKİ her modüle uygulanır.
EXEMPT = frozenset({SRC / "jev.py", SRC / "jev_budget.py"})
BUDGET_MODULE = SRC / "jev_budget.py"
LABELS = "".join(
    f'{{"title":"{title}","url":"u{n}","language":"tr","team":"Galatasaray","relevant":true}}\n'
    for n, title in enumerate(("a", "b"))
)


def _explode(*_a: object, **_k: object) -> Any:
    raise AssertionError("anahtarsız komut veritabanına bağlanmamalı")


def _fake_jev() -> FakeJev:
    return FakeJev(ChoiceAnswer(choice="relevant", confidence=0.9, probabilities={}))


def _connections(
    monkeypatch: pytest.MonkeyPatch, *, total: Decimal = Decimal("0")
) -> list[FakeSpendConn]:
    opened: list[FakeSpendConn] = []

    def _connect() -> FakeSpendConn:
        conn = FakeSpendConn(total=total)
        opened.append(conn)
        return conn

    monkeypatch.setattr(collect, "connect", _connect)
    return opened


def _spend(opened: list[FakeSpendConn]) -> FakeSpendConn:
    (spend,) = [conn for conn in opened if conn.autocommit]
    return spend


def _map_entities(monkeypatch: pytest.MonkeyPatch, jev: FakeJev) -> None:
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setattr(collect, "TypeSafeJev", lambda: jev)
    monkeypatch.setattr(collect, "canonical_team_names", lambda conn, league: ("Galatasaray",))

    def resolve(
        conn: object, client: Any, source: str, league: str, canonical: object, now: object
    ) -> MappingReport:
        for alias in ("Galatasaray Istanbul", "Cimbom"):
            client.ask_choice({"alias": alias}, "hangisi?", {"Galatasaray": "Galatasaray"})
        return MappingReport(written=0, resolutions=())

    monkeypatch.setattr(collect, "resolve_source_aliases", resolve)


# ── map-entities ───────────────────────────────────────────────────────────────────────────


def test_map_entities_records_every_jev_call_in_the_spend_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jev = _fake_jev()
    _map_entities(monkeypatch, jev)
    opened = _connections(monkeypatch)

    assert collect.main(["map-entities", "--league", "tur.1"]) == 0

    assert len(jev.seen) == 2
    assert _spend(opened).kinds == [KIND_CHOICE, KIND_CHOICE]


def test_map_entities_on_the_cap_exits_by_name_without_calling_jev(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    jev = _fake_jev()
    _map_entities(monkeypatch, jev)
    _connections(monkeypatch, total=Decimal(str(MONTHLY_CAP_USD)))

    assert collect.main(["map-entities", "--league", "tur.1"]) == EXIT_BUDGET == 16

    assert jev.seen == []
    assert "tavan" in capsys.readouterr().out


def test_map_entities_without_a_key_exits_by_name_before_touching_the_database(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setattr(collect, "connect", _explode)

    assert collect.main(["map-entities", "--league", "tur.1"]) == EXIT_NO_JEV_KEY == 17
    assert "TYPESAFE_API_KEY" in capsys.readouterr().out


# ── calibrate ──────────────────────────────────────────────────────────────────────────────


def test_calibrate_records_every_jev_call_in_the_spend_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "tr.jsonl").write_text(LABELS, encoding="utf-8")
    jev = _fake_jev()
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setattr(collect, "TypeSafeJev", lambda: jev)
    opened = _connections(monkeypatch)

    assert collect._calibrate_command("tr", calibration_dir=tmp_path) == 0

    assert len(jev.seen) == 2
    assert _spend(opened).kinds == [KIND_CHOICE, KIND_CHOICE]


def test_calibrate_on_the_cap_exits_by_name_and_writes_no_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "tr.jsonl").write_text(LABELS, encoding="utf-8")
    jev = _fake_jev()
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setattr(collect, "TypeSafeJev", lambda: jev)
    _connections(monkeypatch, total=Decimal(str(MONTHLY_CAP_USD)))

    assert collect._calibrate_command("tr", calibration_dir=tmp_path) == EXIT_BUDGET

    assert jev.seen == []
    assert not (tmp_path / "tr.report.json").exists()
    assert "tavan" in capsys.readouterr().out


def test_calibrate_without_a_key_exits_by_name_before_touching_the_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "tr.jsonl").write_text(LABELS, encoding="utf-8")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setattr(collect, "connect", _explode)

    assert collect._calibrate_command("tr", calibration_dir=tmp_path) == EXIT_NO_JEV_KEY
    assert "TYPESAFE_API_KEY" in capsys.readouterr().out


# ── Kaynak kuralı: `TypeSafeJev` yalnız `BudgetedJev` içinden çağrılır ──────────────────────


def _name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _wrappers(tree: ast.Module) -> frozenset[str]:
    """`BudgetedJev` ve ilk parametresini `BudgetedJev`in ilk argümanı yapan modül fonksiyonları."""
    found = {"BudgetedJev"}
    for func in ast.walk(tree):
        if not isinstance(func, ast.FunctionDef) or not func.args.args:
            continue
        first = func.args.args[0].arg
        if any(
            isinstance(call, ast.Call)
            and _name(call.func) == "BudgetedJev"
            and call.args
            and isinstance(call.args[0], ast.Name)
            and call.args[0].id == first
            for call in ast.walk(func)
        ):
            found.add(func.name)
    return frozenset(found)


def _parents(tree: ast.Module) -> dict[ast.AST, ast.AST]:
    return {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}


def _wrapped(node: ast.AST, parents: dict[ast.AST, ast.AST], wrappers: frozenset[str]) -> bool:
    call = parents.get(node)
    return (
        isinstance(call, ast.Call)
        and _name(call.func) in wrappers
        and bool(call.args)
        and call.args[0] is node
    )


def _enclosing(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> ast.AST | None:
    current = parents.get(node)
    while current is not None and not isinstance(current, ast.FunctionDef):
        current = parents.get(current)
    return current


def _bound_and_wrapped(
    call: ast.Call, parents: dict[ast.AST, ast.AST], wrappers: frozenset[str]
) -> bool:
    """`x = TypeSafeJev()` ve fonksiyonda `x`in HER okunuşu bir sarmalayıcının ilk argümanı."""
    assign = parents.get(call)
    if not (
        isinstance(assign, ast.Assign)
        and len(assign.targets) == 1
        and isinstance(assign.targets[0], ast.Name)
    ):
        return False
    func = _enclosing(assign, parents)
    if func is None:
        return False
    bound = assign.targets[0].id
    uses = [
        node
        for node in ast.walk(func)
        if isinstance(node, ast.Name) and node.id == bound and isinstance(node.ctx, ast.Load)
    ]
    return bool(uses) and all(_wrapped(use, parents, wrappers) for use in uses)


def _call_sites() -> Iterator[tuple[str, bool]]:
    """(yer, sarılı mı) — `TypeSafeJev`e her başvuru; çağrı olmayan (fabrika) sarılı sayılmaz."""
    for path in sorted(SRC.rglob("*.py")):
        if path in EXEMPT:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        parents = _parents(tree)
        # Bütçe modülünün kendi sarmalayıcıları (`budgeted_jev`) import edilip çağrılır; o modülün
        # SARMAYAN fonksiyonları tanınmaz — `_wrappers` yalnız `BudgetedJev(ilk_param, …)` kuranları
        # sayar.
        wrappers = _wrappers(tree) | _wrappers(ast.parse(BUDGET_MODULE.read_text(encoding="utf-8")))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Name | ast.Attribute) and _name(node) == "TypeSafeJev"):
                continue
            where = f"{path.relative_to(SRC)}:{node.lineno}"
            call = parents.get(node)
            if isinstance(call, ast.Call) and call.func is node:
                yield (
                    where,
                    _wrapped(call, parents, wrappers)
                    or _bound_and_wrapped(call, parents, wrappers),
                )
            else:
                yield where, False  # fabrika olarak geçirilen sınıf: kim, nerede kurar bilinmez


def test_every_type_safe_jev_outside_the_budget_module_is_wrapped_in_budgeted_jev() -> None:
    sites = list(_call_sites())

    assert {where.split(":")[0] for where, _ in sites} >= {"collect.py", "features/__main__.py"}
    assert [where for where, wrapped in sites if not wrapped] == []
