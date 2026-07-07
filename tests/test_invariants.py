"""Property-based invariant tests for the simulation engine.

Phase 11 — Tests 45-52.
Uses Hypothesis to explore valid config spaces and verify invariants.
"""

from __future__ import annotations

import json
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from simulation.engine import Engine
from simulation.llm_interface import StubLLM
from simulation.config import load_config

# Derive valid actions from engine's action aliases
VALID_ACTIONS = set(Engine._ACTION_ALIASES.values())

# ─── config strategies ──────────────────────────────────────────────

n_agents = st.integers(min_value=2, max_value=5)
n_rounds = st.integers(min_value=1, max_value=4)
n_turns = st.integers(min_value=1, max_value=3)
fish_amt = st.floats(min_value=0.0, max_value=12.0, allow_nan=False, allow_infinity=False)
start_res = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)


# ─── helpers ────────────────────────────────────────────────────────

def p():
    return {"action": "pass", "reasoning": ".", "significance": None}

def fish(amt):
    return {"action": "fish", "amount": amt, "reasoning": ".", "significance": "economic"}

def vote(idx, n):
    return {"vote_for": f"agent_{idx % n}"}

def campaign():
    return {"harvest_limit": 6.0, "penalty_rate": 2.0, "message": ".", "reasoning": "."}


def make_responses(num_agents, turns, rounds, first_elec, fish_amt):
    """Build deterministic stub responses for any config."""
    resp = []
    for r in range(1, rounds + 1):
        # pre-harvest free
        resp.extend([p() for _ in range(num_agents * turns)])
        # election
        if r >= first_elec:
            resp.extend([campaign() for _ in range(num_agents)])
            resp.extend([vote(i, num_agents) for i in range(num_agents)])
        # harvest
        resp.extend([fish(fish_amt) for _ in range(num_agents)])
        # post-harvest free
        resp.extend([p() for _ in range(num_agents * turns)])
    return resp


def run_engine(n_agents_v, n_rounds_v, n_turns_v, fish_amt_v, start_res_v):
    """Build and run the engine for a given config."""
    names = [f"Agent_{i}" for i in range(n_agents_v)]
    first_elec = 2 if n_rounds_v >= 2 else 99

    cfg = load_config({
        "simulation": {"num_rounds": n_rounds_v, "turns_per_phase": n_turns_v},
        "agents": {"names": names, "starting_resources": start_res_v},
        "resources": {"carrying_capacity": 100.0, "regeneration_factor": 1.5},
        "leader": {"fine_destination": "common_pool"},
        "election": {"method": "plurality", "first_election_round": first_elec, "elections_every_round": False},
    })

    responses = make_responses(n_agents_v, n_turns_v, n_rounds_v, first_elec, fish_amt_v)
    llm = StubLLM(responses)
    engine = Engine(cfg, llm=llm, seed=42)
    engine.run()
    return engine


slow = settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])


# ═════════════════════════════════════════════════════════════════════
# Individual test functions with Hypothesis
# ═════════════════════════════════════════════════════════════════════

@slow
@given(n_agents, n_rounds, n_turns, fish_amt, start_res)
def test_pool_never_negative(n_agents, n_rounds, n_turns, fish_amt, start_res):
    """Test 45: Pool amount never drops below 0."""
    engine = run_engine(n_agents, n_rounds, n_turns, fish_amt, start_res)
    for rnd in engine.get_output()["rounds"]:
        for phase in rnd["phases"]:
            for event in phase["turns"]:
                pool = event.get("resources_after", {}).get("pool", 0)
                assert pool >= -1e-9, f"Pool negative: {pool}"


@slow
@given(n_agents, n_rounds, n_turns, fish_amt, start_res)
def test_agent_resources_never_negative(n_agents, n_rounds, n_turns, fish_amt, start_res):
    """Test 46: No agent's resources drop below 0."""
    engine = run_engine(n_agents, n_rounds, n_turns, fish_amt, start_res)
    for rnd in engine.get_output()["rounds"]:
        for phase in rnd["phases"]:
            for event in phase["turns"]:
                after = event.get("resources_after", {})
                for aid, res in after.items():
                    if aid != "pool":
                        assert res >= -1e-9, f"{aid} negative: {res}"


@slow
@given(n_agents, n_rounds, n_turns, fish_amt, start_res)
def test_gini_in_range(n_agents, n_rounds, n_turns, fish_amt, start_res):
    """Test 47: Gini coefficient is always between 0 and 1."""
    engine = run_engine(n_agents, n_rounds, n_turns, fish_amt, start_res)
    for m in engine.get_output()["metrics"]["by_round"]:
        g = m["gini_coefficient"]
        assert 0.0 <= g <= 1.0, f"Gini out of range: {g}"


@slow
@given(n_agents, n_rounds, n_turns, fish_amt, start_res)
def test_valid_action_types(n_agents, n_rounds, n_turns, fish_amt, start_res):
    """Test 48: Every event has a valid action type."""
    engine = run_engine(n_agents, n_rounds, n_turns, fish_amt, start_res)
    for rnd in engine.get_output()["rounds"]:
        for phase in rnd["phases"]:
            for event in phase["turns"]:
                assert event.get("action", "") in VALID_ACTIONS, \
                    f"Invalid action: '{event.get('action')}'"


@slow
@given(n_agents, n_rounds, n_turns, fish_amt, start_res)
def test_json_serializable(n_agents, n_rounds, n_turns, fish_amt, start_res):
    """Test 49: Output is JSON-serializable."""
    engine = run_engine(n_agents, n_rounds, n_turns, fish_amt, start_res)
    json.dumps(engine.get_output())


@slow
@given(n_agents, n_rounds, n_turns, fish_amt, start_res)
def test_leader_field_consistency(n_agents, n_rounds, n_turns, fish_amt, start_res):
    """Test 50: Election phase present iff round >= first_election_round."""
    engine = run_engine(n_agents, n_rounds, n_turns, fish_amt, start_res)
    first_elec = engine.config["election"].get("first_election_round", 99)
    for rnd in engine.get_output()["rounds"]:
        names = [p["phase"] for p in rnd["phases"]]
        if first_elec and rnd["round"] >= first_elec:
            assert "election" in names
        else:
            assert "election" not in names


@slow
@given(n_agents, n_rounds, n_turns, fish_amt, start_res)
def test_metrics_recorded(n_agents, n_rounds, n_turns, fish_amt, start_res):
    """Test 51: Metrics recorded for every round."""
    engine = run_engine(n_agents, n_rounds, n_turns, fish_amt, start_res)
    metrics = engine.get_output()["metrics"]["by_round"]
    assert len(metrics) == n_rounds, f"Expected {n_rounds} metric entries, got {len(metrics)}"
    for m in metrics:
        assert "total_harvest" in m
        assert "pool_remaining" in m
        assert "gini_coefficient" in m


@slow
@given(n_agents, n_rounds, n_turns, fish_amt, start_res)
def test_completes_without_error(n_agents, n_rounds, n_turns, fish_amt, start_res):
    """Test 52: Engine completes for any valid config."""
    engine = run_engine(n_agents, n_rounds, n_turns, fish_amt, start_res)
    assert engine.get_output()["rounds"] is not None


# ─── pytest smoke tests (quick feedback, no Hypothesis overhead) ───

class TestInvariantSmoke:
    """Quick deterministic checks without Hypothesis."""

    def test_small_simulation_smoke(self):
        engine = run_engine(2, 1, 1, 3.0, 50.0)
        assert engine.get_output()["rounds"][0]["round"] == 1

    def test_large_simulation_smoke(self):
        engine = run_engine(5, 4, 3, 5.0, 50.0)
        assert len(engine.get_output()["rounds"]) == 4

    def test_all_agents_have_events(self):
        engine = run_engine(4, 2, 2, 4.0, 50.0)
        agents_seen = set()
        for rnd in engine.get_output()["rounds"]:
            for phase in rnd["phases"]:
                for event in phase["turns"]:
                    agents_seen.add(event["agent"])
        assert len(agents_seen) == 4
