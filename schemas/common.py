"""Building blocks shared by every report type and by season memory."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    """Base for every model the agent writes: unknown keys are an error, so a
    typo in skill output fails validation instead of silently disappearing."""
    model_config = ConfigDict(extra="forbid")


# A string the frontend renders as markdown (sanitised), not as plain text.
Prose = Annotated[str, Field(json_schema_extra={"format": "markdown"})]

# Player status from the mandatory live status check (CLAUDE.md).
StatusTag = Literal["ACTIVE", "Q", "D", "O", "IR", "SUSP", "UNCONFIRMED"]


class PlayerRef(Strict):
    """A player mention. `player_id` (ESPN id, same in fantasy and site APIs)
    is the join key; `name` is display-only."""
    player_id: int
    name: str
    pro_team: str | None = None
    position: str | None = None


class Consensus(Strict):
    """Our read against expert consensus, always with the reason."""
    tag: Literal["AGREE", "DIVERGE_UP", "DIVERGE_DOWN"]
    reason: str = Field(min_length=1)


class Verdict(Strict):
    call: str = Field(min_length=1)
    confidence: Literal["low", "medium", "high"]


class GlossaryEntry(Strict):
    """Plain-language definition of a stat or term used in the report."""
    term: str = Field(min_length=1)
    definition: str = Field(min_length=1)


class Source(Strict):
    """A cited source: what it is, where, and what it was used for."""
    label: str = Field(min_length=1)
    url: str | None = None
    used_for: str | None = None
