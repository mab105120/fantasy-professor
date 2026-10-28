"""Season memory: read, propose, apply (spec §7, plan §5)."""
from datetime import date, datetime

from pydantic import ValidationError

from schemas.memory import (AddOp, CloseOp, ItemFields, MemoryItem, Proposal, ProposalInput,
                            Proposals, SeasonMemory, SupersedeOp, UpdateOp)

from .paths import Paths, write_json_atomic
from .reports import format_errors


class MemoryError_(Exception):
    pass


def load(paths: Paths) -> SeasonMemory:
    raw = paths.read_json(paths.memory)
    if raw is None:
        league = paths.read_json(paths.data / "league.json") or {}
        return SeasonMemory(season=league.get("year", date.today().year))
    return SeasonMemory.model_validate(raw)


def save(paths: Paths, mem: SeasonMemory) -> None:
    write_json_atomic(paths.memory, mem.model_dump(mode="json", exclude_none=True))


def load_proposals(paths: Paths) -> Proposals:
    raw = paths.read_json(paths.proposals)
    return Proposals() if raw is None else Proposals.model_validate(raw)


def save_proposals(paths: Paths, props: Proposals) -> None:
    write_json_atomic(paths.proposals, props.model_dump(mode="json", exclude_none=True))


# ---------- reading

def select(mem: SeasonMemory, *, open_only=False, kind=None, player=None, team=None) -> list[MemoryItem]:
    out = []
    for it in mem.items:
        if open_only and it.status != "open":
            continue
        if kind and it.kind != kind:
            continue
        if player is not None and player not in {p.player_id for p in it.players}:
            continue
        if team is not None and team not in it.team_ids:
            continue
        out.append(it)
    order = {"action": 0, "watch": 1, "position": 2}
    return sorted(out, key=lambda i: (i.status != "open", order[i.kind], i.id))


def line(it: MemoryItem) -> str:
    state = "current" if it.kind == "position" and it.status == "open" else it.status
    when = f"W{it.week}" + (f"→W{it.revisit_week}" if it.revisit_week else "")
    text = f"{it.id}  {it.kind.upper():<8} {state:<10} {when:<7} {it.summary}"
    if it.trigger:
        text += f"  [trigger: {it.trigger}]"
    if it.outcome:
        text += f"  [outcome: {it.outcome}]"
    return text


# ---------- proposing

def propose(paths: Paths, entries: list, source: str) -> list[Proposal]:
    """Stage operations for confirmation. Validates each op and checks that
    referenced ids exist, so a bad proposal fails now, not at apply time."""
    if isinstance(entries, dict):
        entries = [entries]
    mem = load(paths)
    ids = {i.id for i in mem.items}
    props = load_proposals(paths)
    nxt = 1 + max([int(p.proposal_id[1:]) for p in props.proposals] or [0])
    added = []
    for n, raw in enumerate(entries):
        try:
            inp = ProposalInput.model_validate(raw)
        except ValidationError as e:
            raise MemoryError_(f"proposal #{n + 1} failed validation:\n" + format_errors(e)) from None
        if not isinstance(inp.op, AddOp) and inp.op.id not in ids:
            raise MemoryError_(f"proposal #{n + 1}: no memory item {inp.op.id!r}")
        p = Proposal(proposal_id=f"p{nxt:03d}", created=datetime.now().astimezone().replace(microsecond=0),
                     source=source, rationale=inp.rationale, op=inp.op)
        nxt += 1
        props.proposals.append(p)
        added.append(p)
    save_proposals(paths, props)
    return added


def describe(p: Proposal) -> str:
    op = p.op
    if isinstance(op, AddOp):
        what = f"ADD {op.item.kind}: {op.item.summary}"
    elif isinstance(op, CloseOp):
        what = f"CLOSE {op.id}: {op.outcome}"
    elif isinstance(op, UpdateOp):
        what = f"UPDATE {op.id}: " + ", ".join(f"{k}={v!r}" for k, v in op.set.items())
    else:
        what = f"SUPERSEDE {op.id} with {op.item.kind}: {op.item.summary}"
    return f"{p.proposal_id}  {what}" + (f"  — {p.rationale}" if p.rationale else "") + f"  ({p.source})"


# ---------- applying

def _new_item(mem: SeasonMemory, fields: ItemFields, today: date) -> MemoryItem:
    nxt = 1 + max([int(i.id[1:]) for i in mem.items] or [0])
    return MemoryItem(id=f"m{nxt:03d}", created=today, updated=today, **fields.model_dump())


def apply_op(mem: SeasonMemory, op, today: date) -> str:
    by_id = {i.id: i for i in mem.items}
    if isinstance(op, AddOp):
        item = _new_item(mem, op.item, today)
        if op.status == "closed":
            try:
                item = MemoryItem.model_validate(item.model_dump() | {"status": "closed", "closed": today})
            except ValidationError as e:
                raise MemoryError_("closed item is invalid:\n" + format_errors(e)) from None
        mem.items.append(item)
        return item.id
    target = by_id.get(op.id)
    if target is None:
        raise MemoryError_(f"no memory item {op.id!r}")
    if isinstance(op, CloseOp):
        data = target.model_dump() | {"status": "closed", "outcome": op.outcome, "closed": today, "updated": today}
    elif isinstance(op, UpdateOp):
        data = target.model_dump() | op.set | {"updated": today}
    else:  # SupersedeOp
        item = _new_item(mem, op.item, today)
        item = item.model_copy(update={"supersedes": target.id})
        mem.items.append(item)
        data = target.model_dump() | {"status": "superseded", "superseded_by": item.id, "closed": today, "updated": today}
    try:
        new = MemoryItem.model_validate(data)
    except ValidationError as e:
        raise MemoryError_(f"applying to {op.id} would make it invalid:\n" + format_errors(e)) from None
    mem.items[mem.items.index(target)] = new
    return new.id


def apply(paths: Paths, proposal_ids: list[str] | None, today: date | None = None) -> list[str]:
    """Apply the given proposals (all when None) in order, atomically: if any
    fails, nothing is written."""
    today = today or date.today()
    mem, props = load(paths), load_proposals(paths)
    wanted = [p for p in props.proposals if proposal_ids is None or p.proposal_id in proposal_ids]
    missing = set(proposal_ids or []) - {p.proposal_id for p in wanted}
    if missing:
        raise MemoryError_(f"unknown proposal ids: {sorted(missing)}")
    results = [f"{p.proposal_id} → {apply_op(mem, p.op, today)}" for p in wanted]
    SeasonMemory.model_validate(mem.model_dump())
    save(paths, mem)
    done = {p.proposal_id for p in wanted}
    props.proposals = [p for p in props.proposals if p.proposal_id not in done]
    save_proposals(paths, props)
    return results


def reject(paths: Paths, proposal_ids: list[str]) -> int:
    props = load_proposals(paths)
    before = len(props.proposals)
    props.proposals = [p for p in props.proposals if p.proposal_id not in set(proposal_ids)]
    save_proposals(paths, props)
    return before - len(props.proposals)
