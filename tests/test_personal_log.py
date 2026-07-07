"""Tests for agent personal_log and relevant_log methods.

Phase: Personal Log — Agent-level data model.
"""

import pytest
from simulation.agent import Agent


class TestPersonalLogDataModel:
    """Tests for personal_log storage on Agent."""

    def test_personal_log_starts_empty(self):
        agent = Agent(id="alice", name="Alice", resources=50.0)
        assert agent.personal_log == []

    def test_add_log_entry_stores_fields(self):
        agent = Agent(id="alice", name="Alice", resources=50.0)
        agent.add_log_entry(
            round_num=1, turn=3, phase="free_interaction",
            type="talk", data={"channel": "public", "speaker": "Bob", "message": "hello"}
        )
        assert len(agent.personal_log) == 1
        entry = agent.personal_log[0]
        assert entry["round"] == 1
        assert entry["turn"] == 3
        assert entry["phase"] == "free_interaction"
        assert entry["type"] == "talk"
        assert entry["data"]["channel"] == "public"
        assert entry["data"]["message"] == "hello"

    def test_add_log_entry_append_order(self):
        agent = Agent(id="alice", name="Alice", resources=50.0)
        agent.add_log_entry(1, 1, "free_interaction", "system", {"text": "first"})
        agent.add_log_entry(1, 2, "free_interaction", "system", {"text": "second"})
        assert len(agent.personal_log) == 2
        assert agent.personal_log[0]["data"]["text"] == "first"
        assert agent.personal_log[1]["data"]["text"] == "second"

    def test_add_log_entry_no_turn(self):
        """Must work without a turn (e.g. round markers)."""
        agent = Agent(id="alice", name="Alice", resources=50.0)
        agent.add_log_entry(round_num=1, turn=None, phase=None, type="system", data={"text": "Round 1"})
        assert len(agent.personal_log) == 1
        assert agent.personal_log[0]["turn"] is None

    def test_multiple_agents_independent_logs(self):
        a1 = Agent(id="a", name="A", resources=50.0)
        a2 = Agent(id="b", name="B", resources=50.0)
        a1.add_log_entry(1, 1, "free_interaction", "talk", {"channel": "public", "speaker": "A", "message": "hi"})
        assert len(a1.personal_log) == 1
        assert len(a2.personal_log) == 0
