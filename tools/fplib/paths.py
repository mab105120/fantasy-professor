import json
import os
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Paths:
    root: Path = REPO

    @property
    def data(self) -> Path: return self.root / "data"
    @property
    def reports(self) -> Path: return self.root / "reports"
    @property
    def state(self) -> Path: return self.root / "state"
    @property
    def run(self) -> Path: return self.root / ".run"
    @property
    def sync_meta(self) -> Path: return self.data / "sync_meta.json"
    @property
    def memory(self) -> Path: return self.state / "season.json"
    @property
    def proposals(self) -> Path: return self.state / "proposals.json"
    @property
    def espn_client(self) -> Path: return self.root / "tools" / "espn_client.py"

    def read_json(self, path: Path, default=None):
        return json.loads(path.read_text()) if path.exists() else default

    def current_week(self) -> int:
        league = self.read_json(self.data / "league.json")
        if not league:
            raise SystemExit("data/league.json missing — run a sync first (fp fresh <capability>)")
        return int(league["current_week"])


def write_json_atomic(path: Path, obj) -> None:
    """Write via a temp file + rename so readers (the app's watcher) never see
    a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(path)
