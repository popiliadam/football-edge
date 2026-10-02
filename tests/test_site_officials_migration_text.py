"""0015 METNİ (spec 2026-10-02 §5): her kapıda, DB'siz.

Yorumlar ayıklanır, yorumdaki kelime sayılmaz.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.sql_text import statements
from tests.test_site_migration_text import _select_items

MIGRATION = Path(__file__).resolve().parent.parent / "db/migrations/0015_match_officials.sql"
_VIEW = re.compile(
    r"create or replace view site\.match_officials with \(security_barrier\) as (.*)"
)


def _statements() -> list[str]:
    return statements(MIGRATION.read_text(encoding="utf-8"))


def _view() -> str:
    (body,) = [found.group(1) for text in _statements() if (found := _VIEW.fullmatch(text))]
    return body


def test_0015_bounds_its_lock_wait_like_0014() -> None:
    assert (_statements()[0], _statements()[-1]) == (
        "set lock_timeout = '5s'",
        "reset lock_timeout",
    )


def test_the_table_is_the_spec_table() -> None:
    assert (
        "create table if not exists public.match_officials ( "
        "id bigint generated always as identity primary key, "
        "match_id text not null references public.matches(id), "
        "referee text not null check (length(referee) between 1 and 80), "
        "seen_at timestamptz not null )"
    ) in _statements()
    assert (
        "create index if not exists match_officials_match_idx "
        "on public.match_officials (match_id, seen_at)"
    ) in _statements()


def test_the_table_is_append_only_and_truncate_guarded() -> None:
    text = _statements()

    assert (
        "create trigger match_officials_append_only before update or delete "
        "on public.match_officials for each row execute function public.forbid_ledger_mutation()"
    ) in text
    assert (
        "create trigger match_officials_no_truncate before truncate on public.match_officials "
        "for each statement execute function public.forbid_ledger_mutation()"
    ) in text


def test_rls_is_on_without_force_or_policy_and_the_api_roles_lose_everything() -> None:
    text = _statements()
    joined = " ".join(text)

    assert "alter table public.match_officials enable row level security" in text
    assert "force row level security" not in joined and "create policy" not in joined
    assert "revoke all on public.match_officials from anon, authenticated" in text
    assert "revoke all on sequence public.match_officials_id_seq from anon, authenticated" in text
    assert "revoke all on site.match_officials from anon, authenticated, service_role" in text


def test_the_view_reads_only_the_table_and_site_matches_and_is_not_invoker() -> None:
    sources = set(re.findall(r"\b(?:from|join) ([\w.]+)", _view()))

    assert sources == {"public.match_officials", "site.matches"}
    assert all("security_invoker" not in text for text in _statements())


@pytest.mark.leakage
def test_the_view_shows_the_last_assignment_seen_before_kickoff() -> None:
    body = _view()

    assert _select_items(body) == ("distinct on (o.match_id) o.match_id", "o.referee")
    assert "join site.matches m on m.id = o.match_id" in body
    assert "where o.seen_at < m.commence_time" in body
    assert body.endswith("order by o.match_id, o.seen_at desc, o.id desc")
    assert "public_floor" not in body, "taban site.matches join'inden gelir"


def test_the_only_grant_is_select_on_the_view_to_site_reader() -> None:
    grants = [text for text in _statements() if text.startswith("grant ")]
    joined = " ".join(_statements())

    assert grants == ["grant select on site.match_officials to site_reader"]
    assert re.search(r"\blogin\b", joined) is None and re.search(r"\bpassword\b", joined) is None
