"""Season memory (spec §7, plan §5): the agent's continuity.

Three kinds of item:
  action    something we did that awaits or has an outcome (trade sent, claim made)
  watch     something to check later, with a trigger and a week to revisit
  position  a standing call that holds until revised (cut order, "hold Barkley")

Changes are never written directly: a skill stages operations as proposals,
Mo confirms, and only then are they applied (`fp memory propose/apply`).
"""
from datetime import date, datetime
from typing import Annotated, Any, Literal, Union

from pydantic import Field, model_validator

from .common import PlayerRef, Strict

Kind = Literal["action", "watch", "position"]


class ItemFields(Strict):
    """The content of an item, as a skill proposes it (no id/dates/status)."""
    kind: Kind
    week: int = Field(ge=1, le=18)
    summary: str = Field(min_length=1)
    detail: str | None = None
    players: list[PlayerRef] = []
    team_ids: list[int] = []
    outcome: str | None = None
    trigger: str | None = None          # watch items: the condition that changes the call
    revisit_week: int | None = Field(default=None, ge=1, le=18)

    @model_validator(mode="after")
    def _kind_rules(self):
        if self.kind == "watch" and not (self.trigger and self.revisit_week):
            raise ValueError("a watch item needs a trigger and a revisit_week")
        if self.kind == "position" and self.trigger:
            raise ValueError("a position has no trigger; use a watch item")
        return self


class MemoryItem(ItemFields):
    id: str = Field(pattern=r"^m\d{3,}$")
    status: Literal["open", "closed", "superseded"] = "open"
    created: date
    updated: date
    closed: date | None = None
    supersedes: str | None = None
    superseded_by: str | None = None

    @model_validator(mode="after")
    def _status_rules(self):
        if self.kind == "action" and self.status == "closed" and not self.outcome:
            raise ValueError(f"{self.id}: a closed action needs an outcome")
        return self


class SeasonMemory(Strict):
    schema_version: int = 1
    season: int
    items: list[MemoryItem] = []


# ---------- proposals (operations awaiting Mo's confirmation)

class AddOp(Strict):
    """Add an item. `status: closed` records something already finished
    (e.g. a past trade offer and its answer); it must carry an outcome."""
    op: Literal["add"]
    item: ItemFields
    status: Literal["open", "closed"] = "open"


class CloseOp(Strict):
    op: Literal["close"]
    id: str
    outcome: str = Field(min_length=1)


UPDATABLE = ("summary", "detail", "players", "team_ids", "outcome", "trigger", "revisit_week", "week")


class UpdateOp(Strict):
    op: Literal["update"]
    id: str
    set: dict[str, Any]

    @model_validator(mode="after")
    def _only_updatable(self):
        bad = sorted(set(self.set) - set(UPDATABLE))
        if bad:
            raise ValueError(f"cannot update {bad}; allowed: {list(UPDATABLE)}")
        return self


class SupersedeOp(Strict):
    """Replace a standing position (or any item) with a new one."""
    op: Literal["supersede"]
    id: str
    item: ItemFields


Op = Annotated[Union[AddOp, CloseOp, UpdateOp, SupersedeOp], Field(discriminator="op")]


class Proposal(Strict):
    proposal_id: str = Field(pattern=r"^p\d{3,}$")
    created: datetime
    source: str                       # which skill / conversation proposed it
    rationale: str | None = None
    op: Op


class Proposals(Strict):
    proposals: list[Proposal] = []


class ProposalInput(Strict):
    """What a skill hands to `fp memory propose` (ids/dates assigned by fp)."""
    rationale: str | None = None
    op: Op
