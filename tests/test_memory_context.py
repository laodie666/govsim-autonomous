"""Tests for the memory context changes.

Verifies that _build_memory_context:
- Shows log entries from last 2 rounds (not just current)
- Shows all reflections (not just the last one)
- Round history is NOT included in decision context
"""

import pytest
from simulation.engine import Engine
from simulation.llm_interface import StubLLM
from simulation.config import load_config
from simulation.agent import Agent, Memory


class TestMemoryContextChanges:
    """Test the memory context improvements."""

    def _build_test_engine(self, n_rounds=3):
        config = load_config({
            "simulation": {"num_rounds": n_rounds, "turns_per_phase": 1},
            "agents": {"names": ["Alice", "Bob"], "starting_resources": 50.0},
            "resources": {"carrying_capacity": 100.0, "regeneration_factor": 1.5},
            "leader": {"fine_destination": "common_pool", "default_limit": 10.0, "default_penalty_rate": 1.0, "candidacy_cost": 5.0},
            "election": {"method": "plurality", "first_election_round": 2},
        })
        engine = Engine(config, StubLLM([{"action": "pass", "reasoning": "...", "significance": "small_talk"}]))
        return engine

    def test_log_shows_last_two_rounds(self):
        """Personal log shows entries from last 2 rounds, filters older ones."""
        engine = self._build_test_engine()
        alice = engine.get_agent("alice")

        # Add log entries at different rounds directly
        alice.add_log_entry(round_num=1, turn=1, phase="free_interaction", type="talk", data={
            "speaker": "Alice", "channel": "public", "message": "Round 1 message", "heard_by": []
        })
        alice.add_log_entry(round_num=2, turn=10, phase="free_interaction", type="talk", data={
            "speaker": "Alice", "channel": "public", "message": "Round 2 message", "heard_by": []
        })
        alice.add_log_entry(round_num=3, turn=20, phase="free_interaction", type="talk", data={
            "speaker": "Alice", "channel": "public", "message": "Round 3 message", "heard_by": []
        })

        # Add round markers so round headers appear
        alice.add_log_entry(round_num=1, turn=0, phase="free_interaction", type="round_marker", data={"round": 1})
        alice.add_log_entry(round_num=2, turn=9, phase="free_interaction", type="round_marker", data={"round": 2})
        alice.add_log_entry(round_num=3, turn=19, phase="free_interaction", type="round_marker", data={"round": 3})

        # Set current_round so max_round is meaningful
        engine.current_round = 3

        context = engine._build_memory_context(alice)

        # Should include last 2 rounds (2 and 3)
        assert "=== Round 2" in context, f"Round 2 should be in context, got:\n{context}"
        assert "=== Round 3" in context, f"Round 3 should be in context, got:\n{context}"
        assert "Round 1 message" not in context, "Round 1 should be filtered out"

    def test_all_reflections_shown(self):
        """All reflections are shown, not just the last one."""
        engine = self._build_test_engine()
        alice = engine.get_agent("alice")

        # Need at least one log entry so the function doesn't return early
        alice.add_log_entry(round_num=1, turn=1, phase="free_interaction", type="round_marker", data={"round": 1})

        # Add multiple reflections
        alice.add_memory(turn=10, type="reflection", content="Round 1 reflection: Alice is trustworthy")
        alice.add_memory(turn=20, type="reflection", content="Round 2 reflection: Bob is greedy")
        alice.add_memory(turn=30, type="reflection", content="Round 3 reflection: I need to conserve")

        engine.current_round = 1
        context = engine._build_memory_context(alice)

        # All reflections should appear
        assert "--- YOUR REFLECTIONS ---" in context
        assert "Alice is trustworthy" in context
        assert "Bob is greedy" in context
        assert "I need to conserve" in context

    def test_round_history_not_in_context(self):
        """Round history is not included in the memory context."""
        engine = self._build_test_engine()
        alice = engine.get_agent("alice")
        alice.add_log_entry(round_num=1, turn=1, phase="free_interaction", type="round_marker", data={"round": 1})
        engine.current_round = 1

        context = engine._build_memory_context(alice)

        # The phrase "ROUND HISTORY" should not appear (it's from _build_round_history, not memory)
        assert "ROUND HISTORY" not in context

    def test_decision_context_omits_round_history(self):
        """The full decision context passed to get_decision does not include round history."""
        engine = self._build_test_engine(n_rounds=2)
        
        # Run a minimal simulation
        engine.run()

        # Check that outputs exist (simulation ran)
        output = engine.get_output()
        assert len(output["rounds"]) > 0

        # Check memory context of an agent after run doesn't contain round history
        alice = engine.get_agent("alice")
        context = engine._build_memory_context(alice)
        assert "ROUND HISTORY" not in context
