import json

from conftest import FIXTURES
from fplib import usage

SUMMARY = json.loads((FIXTURES / "espn_summary_401872980.json").read_text())  # W5 TB @ DAL


def test_game_usage_rusher():
    g = usage.game_usage(SUMMARY, 4596448)   # Bucky Irving: 21 car of TB's 39
    assert g["week"] == 5 and g["team"] == "TB" and g["opponent"] == "DAL"
    assert (g["carries"], g["team_carries"]) == (21, 39)
    assert g["carry_share"] == round(21 / 39, 3)
    assert g["rushing_yards"] == 165 and g["touchdowns"] >= 1
    assert g["team_pass_attempts"] == 25


def test_game_usage_receiver_share():
    g = usage.game_usage(SUMMARY, 4608810)   # Tez Johnson: 1 target of TB's 25
    assert (g["targets"], g["team_targets"]) == (1, 25)
    assert g["target_share"] == 0.04


def test_player_without_line_returns_none():
    assert usage.game_usage(SUMMARY, 1) is None


def test_abbreviation_fix():
    assert usage.norm("JAC") == "JAX" and usage.norm("WSH") == "WSH"
