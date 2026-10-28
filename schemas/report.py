"""The report envelope (spec §6, plan §3).

Every report file has the same outer shape; only `sections` differs by type.
`fp report write` builds the envelope fields (type, week, created_at,
data_freshness, man_wolf) itself, so a skill only supplies the body:
headline, subject, sections, glossary and sources.

Per-type section models are registered in SECTION_MODELS as each capability
is rebuilt (plan step 3). Until a type has one, its `sections` is accepted as
any JSON object.
"""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from .common import GlossaryEntry, PlayerRef, Source, Strict

ReportType = Literal["review", "waivers", "lineup", "preview", "trade", "player-eval"]
WEEKLY_TYPES = ("review", "waivers", "lineup", "preview")  # one per week, re-run replaces
LAB_TYPES = ("trade", "player-eval")                        # single slot, next run overwrites
REPORT_TYPES = WEEKLY_TYPES + LAB_TYPES

# Body fields a skill writes; everything else in the envelope is owned by fp.
BODY_FIELDS = ("headline", "subject", "sections", "glossary", "sources")

# type -> pydantic model for `sections`; filled in per capability in step 3.
SECTION_MODELS: dict[str, type[BaseModel]] = {}


class ManWolf(Strict):
    record: str                       # "4-1" or "4-1-0"
    standing: int
    opponent_id: int | None = None    # fantasy opponent for the report's week


class Subject(Strict):
    """What a lab report is about (trade partner/players, evaluated players)."""
    label: str | None = None
    players: list[PlayerRef] = []
    team_ids: list[int] = []


class Report(Strict):
    type: ReportType
    schema_version: int = 1
    status: Literal["draft", "final"] = "final"   # draft while sections are still being written
    week: int = Field(ge=1, le=18)
    created_at: datetime
    data_freshness: dict[str, datetime | None] = {}
    man_wolf: ManWolf | None = None
    subject: Subject | None = None
    headline: str = ""
    sections: dict[str, Any] = {}
    glossary: list[GlossaryEntry] = []
    sources: list[Source] = []

    @model_validator(mode="after")
    def _final_needs_headline(self):
        if self.status == "final" and not self.headline.strip():
            raise ValueError("a final report needs a non-empty headline (the call, in one sentence)")
        return self

    @model_validator(mode="after")
    def _typed_sections(self):
        model = SECTION_MODELS.get(self.type)
        if model is not None and self.status == "final":
            model.model_validate(self.sections)
        return self
