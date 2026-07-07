"""Snapshot tests for the simulation engine.

Phase 11 — Tests 53-54.
Generates golden output then compares future runs against it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import pytest

from simulation.engine import Engine
from simulation.llm_interface import StubLLM
from simulation.config import load_config

GOLDEN_DIR = Path(__file__).parent / "fixtures" / "golden"
GOLDEN_FILE = GOLDEN_DIR / "snapshot_output.json"


def p():
    return {"action": "pass", "reasoning": ".", "significance": None}

def fish(amt):
    return {"action": "fish", "amount": amt, "reasoning": ".", "significance": "economic"}

def vote(cid):
    return {"vote_for": cid}

def campaign(limit=6.0, rate=2.0):
    return {"harvest_limit": limit, "penalty_rate": rate, "message": ".", "reasoning": "."}


def make_golden_engine():
    """Build the canonical engine instance.

    Any change to the simulation that alters deterministic output will
    require regenerating the golden file.
    """
    cfg = load_config({
        "simulation": {"num_rounds": 2, "turns_per_phase": 2},
        "agents": {"names": ["Alice", "Bob", "Charlie"], "starting_resources": 50.0},
        "resources": {"carrying_capacity": 100.0, "regeneration_factor": 1.5},
        "leader": {"fine_destination": "common_pool"},
        "election": {"method": "plurality", "first_election_round": 2},
    })

    responses = (
        # R1 free (6 p)
        [p() for _ in range(6)] +
        # R1 harvest (3 fish)
        [fish(8.0), fish(3.0), fish(7.0)] +
        # R1 post (6 p)
        [p() for _ in range(6)] +
        # R2 free (6 p)
        [p() for _ in range(6)] +
        # R2 election — campaigns
        [campaign(limit=5.0, rate=2.0),
         campaign(limit=8.0, rate=1.0),
         campaign(limit=6.0, rate=3.0)] +
        # R2 election — votes
        [vote("alice"), vote("alice"), vote("bob")] +
        # R2 harvest — Alice fishes 7 (exceeds limit 5, penalty 4)
        [fish(7.0), fish(4.0), fish(5.0)] +
        # R2 post (6 p)
        [p() for _ in range(6)]
    )

    llm = StubLLM(list(responses))
    engine = Engine(cfg, llm=llm, seed=42)
    engine.run()
    return engine


def _normalise_for_comparison(output: dict) -> dict:
    """Strip variable fields (run_id, started_at) before comparison."""
    output = dict(output)
    output.pop("run_id", None)
    output.pop("started_at", None)
    output.pop("config", None)  # config is not part of deterministic output
    return output


def test_generate_golden():
    """Test 53: Generate or update the golden snapshot file.

    When the simulation logic changes, delete the golden file and
    re-run this test to regenerate it.
    """
    if GOLDEN_FILE.exists():
        return  # Already exists — don't overwrite

    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    engine = make_golden_engine()
    output = engine.get_output()
    with open(GOLDEN_FILE, "w") as f:
        json.dump(output, f, indent=2)
    assert GOLDEN_FILE.stat().st_size > 0


def test_against_golden():
    """Test 54: Current output matches the golden snapshot.

    Fails if the simulation logic has changed (intentionally or not).
    Delete tests/fixtures/golden/snapshot_output.json to regenerate.
    """
    if not GOLDEN_FILE.exists():
        pytest.skip("Golden file not found — run tests once to generate it")



    engine = make_golden_engine()
    current = _normalise_for_comparison(engine.get_output())

    with open(GOLDEN_FILE) as f:
        golden = _normalise_for_comparison(json.load(f))

    # Compare rounds
    assert len(current["rounds"]) == len(golden["rounds"])

    for c_round, g_round in zip(current["rounds"], golden["rounds"]):
        assert c_round["round"] == g_round["round"]
        assert len(c_round["phases"]) == len(g_round["phases"])

        for c_phase, g_phase in zip(c_round["phases"], g_round["phases"]):
            assert c_phase["phase"] == g_phase["phase"]
            assert len(c_phase["turns"]) == len(g_phase["turns"])

            for c_event, g_event in zip(c_phase["turns"], g_phase["turns"]):
                # Compare action, agent, amount, target — skip timing/variable fields
                assert c_event["action"] == g_event["action"]
                assert c_event["agent"] == g_event["agent"]
                assert c_event.get("target") == g_event.get("target")
                assert c_event.get("amount") == g_event.get("amount")
                assert c_event.get("is_private") == g_event.get("is_private")
