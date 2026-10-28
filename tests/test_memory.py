from datetime import date

import pytest

from fplib import memory
from fplib.memory import MemoryError_

WATCH = {"op": {"op": "add", "item": {"kind": "watch", "week": 6, "summary": "White's share vs Ekeler",
                                      "trigger": "leads WSH backfield in carries", "revisit_week": 7,
                                      "players": [{"player_id": 4697815, "name": "Rachaad White"}]}}}
ACTION = {"op": {"op": "add", "item": {"kind": "action", "week": 6, "summary": "Sent Gordon packages to Imad",
                                       "team_ids": [15]}}}
POSITION = {"op": {"op": "add", "item": {"kind": "position", "week": 6, "summary": "Cut order: Saints D/ST > Kamara"}}}


def test_propose_does_not_write_memory(proj):
    added = memory.propose(proj, [WATCH, ACTION], source="test")
    assert [p.proposal_id for p in added] == ["p001", "p002"]
    assert memory.load(proj).items == []
    assert not proj.memory.exists()


def test_apply_selected_then_filters(proj):
    memory.propose(proj, [WATCH, ACTION, POSITION], source="test")
    out = memory.apply(proj, ["p001", "p002"], today=date(2026, 10, 18))
    assert out == ["p001 → m001", "p002 → m002"]
    assert [p.proposal_id for p in memory.load_proposals(proj).proposals] == ["p003"]
    mem = memory.load(proj)
    assert [i.id for i in memory.select(mem, player=4697815)] == ["m001"]
    assert [i.id for i in memory.select(mem, team=15)] == ["m002"]
    assert [i.id for i in memory.select(mem, kind="watch")] == ["m001"]


def test_close_needs_existing_id_and_records_outcome(proj):
    memory.propose(proj, [ACTION], source="test")
    memory.apply(proj, None)
    with pytest.raises(MemoryError_, match="no memory item"):
        memory.propose(proj, [{"op": {"op": "close", "id": "m999", "outcome": "x"}}], source="test")
    memory.propose(proj, [{"op": {"op": "close", "id": "m001", "outcome": "Imad rejected all three"}}], source="test")
    memory.apply(proj, None)
    item = memory.load(proj).items[0]
    assert item.status == "closed" and item.outcome == "Imad rejected all three" and item.closed
    assert memory.select(memory.load(proj), open_only=True) == []


def test_supersede_links_both_items(proj):
    memory.propose(proj, [POSITION], source="test")
    memory.apply(proj, None)
    new = {"op": {"op": "supersede", "id": "m001",
                  "item": {"kind": "position", "week": 7, "summary": "Cut order: Kamara > Wicks"}}}
    memory.propose(proj, [new], source="test")
    memory.apply(proj, None)
    old, cur = memory.load(proj).items
    assert old.status == "superseded" and old.superseded_by == "m002"
    assert cur.supersedes == "m001" and cur.status == "open"


def test_apply_is_all_or_nothing(proj):
    memory.propose(proj, [POSITION], source="test")
    memory.apply(proj, None)
    bad = {"op": {"op": "update", "id": "m001", "set": {"trigger": "positions can't have one"}}}
    memory.propose(proj, [WATCH, bad], source="test")
    with pytest.raises(MemoryError_):
        memory.apply(proj, None)
    assert len(memory.load(proj).items) == 1
    assert len(memory.load_proposals(proj).proposals) == 2


def test_reject(proj):
    memory.propose(proj, [WATCH, ACTION], source="test")
    assert memory.reject(proj, ["p002"]) == 1
    assert [p.proposal_id for p in memory.load_proposals(proj).proposals] == ["p001"]


def test_invalid_proposal_names_field(proj):
    with pytest.raises(MemoryError_, match="trigger"):
        memory.propose(proj, [{"op": {"op": "add", "item": {"kind": "watch", "week": 6, "summary": "x"}}}],
                       source="test")


def test_add_closed_action_needs_outcome(proj):
    done = {"op": {"op": "add", "status": "closed",
                   "item": {"kind": "action", "week": 4, "summary": "Stafford to ALI for Hubbard",
                            "outcome": "ALI declined", "team_ids": [1]}}}
    memory.propose(proj, [done], source="test")
    memory.apply(proj, None)
    item = memory.load(proj).items[0]
    assert item.status == "closed" and item.closed
    no_outcome = {"op": {"op": "add", "status": "closed",
                         "item": {"kind": "action", "week": 4, "summary": "x"}}}
    memory.propose(proj, [no_outcome], source="test")
    with pytest.raises(MemoryError_, match="outcome"):
        memory.apply(proj, None)
