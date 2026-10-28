import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from schemas import json_schemas
from schemas.common import Consensus, PlayerRef
from schemas.memory import ItemFields, ProposalInput
from schemas.report import Report

BASE = {"type": "waivers", "week": 6, "created_at": "2026-10-17T21:00:00-05:00", "headline": "Hold"}


def test_report_minimal_valid():
    r = Report.model_validate(BASE)
    assert r.status == "final" and r.sections == {}


def test_unknown_keys_rejected():
    with pytest.raises(ValidationError):
        Report.model_validate(BASE | {"headlnie": "typo"})
    with pytest.raises(ValidationError):
        PlayerRef.model_validate({"player_id": 1, "name": "X", "team": "MIA"})


def test_final_report_needs_headline_but_draft_does_not():
    with pytest.raises(ValidationError, match="headline"):
        Report.model_validate(BASE | {"headline": " "})
    Report.model_validate(BASE | {"headline": "", "status": "draft"})


def test_week_bounds_and_type():
    with pytest.raises(ValidationError):
        Report.model_validate(BASE | {"week": 19})
    with pytest.raises(ValidationError):
        Report.model_validate(BASE | {"type": "recap"})


def test_consensus_needs_reason():
    with pytest.raises(ValidationError):
        Consensus.model_validate({"tag": "DIVERGE_UP", "reason": ""})


def test_watch_item_needs_trigger_and_revisit():
    with pytest.raises(ValidationError, match="trigger"):
        ItemFields.model_validate({"kind": "watch", "week": 6, "summary": "watch White"})
    ItemFields.model_validate({"kind": "watch", "week": 6, "summary": "watch White",
                               "trigger": ">= 55% carry share", "revisit_week": 7})


def test_position_cannot_have_trigger():
    with pytest.raises(ValidationError):
        ItemFields.model_validate({"kind": "position", "week": 6, "summary": "Hold Barkley", "trigger": "x"})


def test_update_op_only_allows_known_fields():
    with pytest.raises(ValidationError, match="cannot update"):
        ProposalInput.model_validate({"op": {"op": "update", "id": "m001", "set": {"status": "closed"}}})


@pytest.mark.parametrize("name, schema", json_schemas().items(), ids=list(json_schemas()))
def test_exported_json_schema_matches_models(name, schema):
    path = Path(__file__).parents[1] / "schemas" / "json" / f"{name}.schema.json"
    assert json.loads(path.read_text()) == schema, f"{path.name} is stale: run `fp report schema`"
