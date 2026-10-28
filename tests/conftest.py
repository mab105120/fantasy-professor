import json
from pathlib import Path

import pytest

from fplib.paths import Paths

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def proj(tmp_path) -> Paths:
    """A minimal project tree: league in week 6, Man Wolf (14) 4-1 vs team 9."""
    data = tmp_path / "data"
    data.mkdir()
    (data / "league.json").write_text(json.dumps({"league_id": 394766, "year": 2026, "current_week": 6}))
    (data / "teams.json").write_text(json.dumps([
        {"team_id": 14, "team_name": "The Man Wolf", "wins": 4, "losses": 1, "ties": 0, "standing": 3,
         "schedule": [{"week": 6, "opponent_team_id": 9}, {"week": 5, "opponent_team_id": 15}],
         "roster": [{"playerId": 4711533, "name": "Ollie Gordon II", "proTeam": "MIA", "position": "RB"}]},
        {"team_id": 9, "team_name": "Chaseing a win", "wins": 1, "losses": 4, "ties": 0, "standing": 9,
         "schedule": [], "roster": []},
    ]))
    (data / "sync_meta.json").write_text(json.dumps({"teams.json": {"synced_at": "2026-10-17T21:27:29", "current_week": 6}}))
    return Paths(root=tmp_path)


def write_json(path: Path, obj) -> Path:
    path.write_text(json.dumps(obj))
    return path
