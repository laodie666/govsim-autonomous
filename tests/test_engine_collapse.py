"""Tests for pool collapse detection."""
import pytest
from simulation.engine import Engine
from simulation.llm_interface import StubLLM
from simulation.config import load_config


def stub(*response_dicts):
    return StubLLM(list(response_dicts))


def p():
    return {"action": "pass", "reasoning": ".", "significance": None}


def fish(amt):
    return {"action": "fish", "amount": amt, "reasoning": ".", "significance": "economic"}


def campaign(limit=10.0, rate=0.0):
    return {"harvest_limit": limit, "penalty_rate": rate,
            "message": ".", "reasoning": "."}


def vote(candidate_id):
    return {"vote_for": candidate_id}


@pytest.fixture
def collapse_config():
    """Config designed to collapse: low capacity, aggressive fishing."""
    return load_config({
        "simulation": {"num_rounds": 10, "turns_per_phase": 1},
        "agents": {"names": ["Alice", "Bob"], "starting_resources": 50.0},
        "resources": {"carrying_capacity": 20.0, "regeneration_factor": 0.5},
        "leader": {"fine_destination": "common_pool"},
        "election": {"method": "plurality", "first_election_round": 2},
    })


@pytest.fixture
def safe_config():
    """Config that should NOT collapse."""
    return load_config({
        "simulation": {"num_rounds": 2, "turns_per_phase": 1},
        "agents": {"names": ["Alice", "Bob"], "starting_resources": 50.0},
        "resources": {"carrying_capacity": 100.0, "regeneration_factor": 2.0},
        "leader": {"fine_destination": "common_pool"},
        "election": {"method": "plurality", "first_election_round": 2},
    })


class TestEngineCollapse:

    def test_engine_has_collapse_fields(self):
        """Engine initialises with collapse fields."""
        config = load_config({
            "simulation": {"num_rounds": 1, "turns_per_phase": 1},
            "agents": {"names": ["Alice"], "starting_resources": 50.0},
            "resources": {"carrying_capacity": 100.0, "regeneration_factor": 1.5},
            "leader": {"fine_destination": "common_pool"},
            "election": {"method": "plurality", "first_election_round": 2},
        })
        engine = Engine(config, llm=stub(p(), fish(100.0), p()), seed=42)
        assert hasattr(engine, "collapsed")
        assert engine.collapsed is False
        assert hasattr(engine, "collapsed_at_round")
        assert engine.collapsed_at_round is None

    def test_pool_collapse_ends_simulation_early(self, collapse_config):
        """When pool hits 0 during harvesting, sim stops immediately."""
        responses = [
            p(), p(),  # R1 free (2 agents x 1 turn)
            fish(20.0),  # Alice fishes -- pool goes 20 -> 0
        ]
        engine = Engine(collapse_config, llm=stub(*responses), seed=42)
        engine.run()

        assert engine.collapsed is True
        assert engine.collapsed_at_round == 1
        assert len(engine.get_output()["rounds"]) == 1

    def test_no_collapse_when_pool_positive(self, safe_config):
        """Sim runs full rounds when pool never hits 0."""
        r1 = [p(), p(), fish(5.0), fish(5.0), p(), p()]
        r2 = [p(), p(), campaign(), campaign(), vote("alice"), vote("alice"),
              fish(5.0), fish(5.0), p(), p()]
        engine = Engine(safe_config, llm=stub(*(r1 + r2)), seed=42)
        engine.run()

        assert engine.collapsed is False
        assert engine.collapsed_at_round is None
        assert len(engine.get_output()["rounds"]) == 2

    def test_collapse_in_later_round(self, collapse_config):
        """Pool collapses partway through a later round."""
        # Round 1: free+harvest+post. Round 2: free+election+harvest+post.
        # Provide fish responses for all harvest turns.
        responses = [
            p(), p(), fish(15.0), fish(0.0), p(), p(),
            # R2: 2 free, 2 campaigns, 2 votes, 2 harvest (explicit fish), 2 post
            p(), p(),
            fish(3.0), fish(0.0),  # Alice fishes 3, Bob 0
            p(), p(),
        ]
        engine = Engine(collapse_config, llm=stub(*responses), seed=42)
        engine.run()

        assert engine.collapsed is True
        assert engine.collapsed_at_round == 2

    def test_collapse_threshold_float_safe(self):
        """Pool with very small remaining amount (< 0.01) should trigger collapse."""
        config = load_config({
            "simulation": {"num_rounds": 3, "turns_per_phase": 1},
            "agents": {"names": ["Alice", "Bob"], "starting_resources": 50.0},
            "resources": {"carrying_capacity": 10.0, "regeneration_factor": 1.0, "fish_per_harvest": 10.0},
            "leader": {"fine_destination": "common_pool"},
            "election": {"method": "plurality", "first_election_round": 2},
        })
        stub_llm = stub(
            p(), p(), fish(10.0), fish(10.0), p(), p(),
        )
        engine = Engine(config, llm=stub_llm, seed=42)
        engine.run()
        assert engine.collapsed, "Pool should have collapsed when amount < 0.01"

    def test_survival_length(self, collapse_config):
        """survival_length reports rounds completed before collapse."""
        responses = [
            p(), p(), fish(15.0), fish(0.0), p(), p(),
            # R2: 2 free, 2 campaigns, 2 votes, 2 harvest, 2 post
            p(), p(),
            fish(3.0), fish(0.0),  # Alice fishes 3, Bob 0
            p(), p(),
        ]
        engine = Engine(collapse_config, llm=stub(*responses), seed=42)
        engine.run()
        assert engine.survival_length == 2


class TestRecorderEndCondition:

    def test_recorder_get_output_has_end_condition(self):
        """Recorder output includes end_condition fields."""
        from simulation.recorder import Recorder
        recorder = Recorder(run_id="test_end")
        output = recorder.get_output()
        assert "end_condition" in output
        assert output["end_condition"] == "time_limit"
        assert "collapsed_at_round" in output
        assert output["collapsed_at_round"] is None
        assert "survival_length" in output

    def test_end_condition_collapse_in_output(self, collapse_config):
        """Collapsed sim output shows end_condition='collapse'."""
        responses = [p(), p(), fish(20.0)]
        engine = Engine(collapse_config, llm=stub(*responses), seed=42)
        engine.run()
        output = engine.get_output()

        assert output["end_condition"] == "collapse"
        assert output["collapsed_at_round"] == 1
        assert output["survival_length"] == 1

    def test_end_condition_time_limit(self, safe_config):
        """Normal sim completion shows end_condition='time_limit'."""
        r1 = [p(), p(), fish(5.0), fish(5.0), p(), p()]
        r2 = [p(), p(), campaign(), campaign(), vote("alice"), vote("alice"),
              fish(5.0), fish(5.0), p(), p()]
        engine = Engine(safe_config, llm=stub(*(r1 + r2)), seed=42)
        engine.run()
        output = engine.get_output()

        assert output["end_condition"] == "time_limit"
        assert output["collapsed_at_round"] is None
        assert output["survival_length"] == 2
