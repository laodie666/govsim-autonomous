"""Tests for event recording and output format.

Phase 6 — TDD Layer 1: pure logic, no LLM.
Tests 24-26 from the specification (schema, non-negative invariants).
"""

import json
import pytest
from simulation.recorder import Recorder
from simulation.config import load_config
from simulation.llm_interface import StubLLM
from simulation.engine import Engine


class TestRecorder:
    """Test 24: Event output schema."""

    def test_recorder_creates_empty_run(self):
        """A fresh recorder has no rounds yet."""
        recorder = Recorder(run_id="test_001")
        output = recorder.get_output()
        assert output["run_id"] == "test_001"
        assert output["rounds"] == []
        assert output["metrics"]["by_round"] == []

    def test_recorder_start_round(self):
        """Starting a round adds it to the output."""
        recorder = Recorder(run_id="test_001")
        recorder.start_round(1)
        output = recorder.get_output()
        assert len(output["rounds"]) == 1
        assert output["rounds"][0]["round"] == 1

    def test_recorder_start_phase(self):
        """Starting a phase within a round."""
        recorder = Recorder(run_id="test_001")
        recorder.start_round(1)
        recorder.start_phase("free_interaction")
        output = recorder.get_output()
        assert len(output["rounds"][0]["phases"]) == 1
        assert output["rounds"][0]["phases"][0]["phase"] == "free_interaction"

    def test_recorder_record_event(self):
        """Recording an event within a phase."""
        recorder = Recorder(run_id="test_001")
        recorder.start_round(1)
        recorder.start_phase("free_interaction")

        recorder.record_event(
            turn=1,
            agent="alice",
            action="public_talk",
            target="bob",
            targets=["bob"],
            is_private=False,
            message="Hello!",
            reasoning="Being friendly",
            significance="small_talk",
            resources_before={"alice": 50.0, "pool": 100.0},
            resources_after={"alice": 50.0, "pool": 100.0},
        )

        output = recorder.get_output()
        phase = output["rounds"][0]["phases"][0]
        assert len(phase["turns"]) == 1
        event = phase["turns"][0]
        assert event["turn"] == 1
        assert event["agent"] == "alice"
        assert event["action"] == "public_talk"
        assert event["target"] == "bob"
        assert event["message"] == "Hello!"
        assert event["significance"] == "small_talk"

    def test_recorder_election_result(self):
        """Recording an election result."""
        recorder = Recorder(run_id="test_001")
        recorder.start_round(2)
        recorder.start_phase("election")

        recorder.record_vote("alice", "bob")
        recorder.record_vote("charlie", "alice")
        recorder.record_election_result(
            winner="alice",
            votes={"alice": 3, "bob": 2},
            voter_map={"alice": "alice", "bob": "bob", "charlie": "alice"},
        )

        output = recorder.get_output()
        phase = output["rounds"][0]["phases"][0]
        assert phase["phase"] == "election"
        assert phase["result"]["winner"] == "alice"
        assert phase["result"]["votes"]["alice"] == 3

    def test_recorder_round_metrics(self):
        """Recording metrics per round."""
        recorder = Recorder(run_id="test_001")
        recorder.start_round(1)
        recorder.record_round_metrics(
            total_harvest=15.0,
            pool_remaining=85.0,
            gini_coefficient=0.12,
            violations=1,
            penalties_imposed=1,
        )
        output = recorder.get_output()
        metrics = output["metrics"]["by_round"][0]
        assert metrics["round"] == 1
        assert metrics["total_harvest"] == 15.0
        assert metrics["gini_coefficient"] == 0.12

    def test_recorder_output_json_serializable(self):
        """The output must be serializable to JSON (for the visualizer)."""
        recorder = Recorder(run_id="test_001")
        recorder.start_round(1)
        recorder.start_phase("free_interaction")
        recorder.record_event(
            turn=1, agent="alice", action="pass",
            target=None, targets=None, is_private=False,
            message=None, reasoning="Nothing", significance=None,
            resources_before={"alice": 50.0, "pool": 100.0},
            resources_after={"alice": 50.0, "pool": 100.0},
        )
        recorder.record_round_metrics(
            total_harvest=0.0, pool_remaining=100.0,
            gini_coefficient=0.0, violations=0, penalties_imposed=0,
        )

        # Must serialize without error
        output = recorder.get_output()
        json_str = json.dumps(output, indent=2)
        assert isinstance(json_str, str)
        assert '"run_id"' in json_str

    def test_set_config(self):
        """set_config stores config for output."""
        recorder = Recorder(run_id="test_002")
        recorder.set_config({"simulation": {"num_rounds": 5}})
        output = recorder.get_output()
        assert output["config"]["simulation"]["num_rounds"] == 5

    def test_to_json(self):
        """to_json returns valid JSON string."""
        recorder = Recorder(run_id="test_003")
        recorder.start_round(1)
        recorder.record_round_metrics()
        json_str = recorder.to_json()
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["run_id"] == "test_003"

    def test_save_to_file(self, tmp_path):
        """save writes output to a JSON file."""
        recorder = Recorder(run_id="test_004")
        recorder.start_round(1)
        recorder.record_round_metrics(total_harvest=25.0)

        out_path = tmp_path / "output.json"
        recorder.save(str(out_path))

        assert out_path.exists()
        with open(out_path) as f:
            data = json.load(f)
        assert data["run_id"] == "test_004"
        assert data["metrics"]["by_round"][0]["total_harvest"] == 25.0

    def test_start_phase_without_round_raises(self):
        """Starting a phase before a round raises RuntimeError."""
        recorder = Recorder(run_id="test_005")
        with pytest.raises(RuntimeError):
            recorder.start_phase("election")

    def test_record_event_without_phase_raises(self):
        """Recording an event before starting a phase raises RuntimeError."""
        recorder = Recorder(run_id="test_006")
        recorder.start_round(1)
        with pytest.raises(RuntimeError):
            recorder.record_event(turn=1, agent="alice", action="pass")

    def test_record_election_result_non_election_phase(self):
        """record_election_result on non-election phase is a silent no-op."""
        recorder = Recorder(run_id="test_007")
        recorder.start_round(1)
        recorder.start_phase("free_interaction")
        # Should not crash, even though this is not an election phase
        recorder.record_election_result(
            winner="alice",
            votes={"alice": 1},
            voter_map={"alice": "alice"},
        )
        output = recorder.get_output()
        phase = output["rounds"][0]["phases"][0]
        assert "result" not in phase  # Not an election phase

    def test_multiple_rounds_event_tracking(self):
        """Events are correctly scoped to rounds."""
        recorder = Recorder(run_id="test_008")

        recorder.start_round(1)
        recorder.start_phase("free_interaction")
        recorder.record_event(turn=1, agent="alice", action="pass")

        recorder.start_round(2)
        recorder.start_phase("free_interaction")
        recorder.record_event(turn=1, agent="bob", action="pass")

        output = recorder.get_output()
        assert len(output["rounds"]) == 2
        assert output["rounds"][0]["phases"][0]["turns"][0]["agent"] == "alice"
        assert output["rounds"][1]["phases"][0]["turns"][0]["agent"] == "bob"

    def test_record_round_metrics_without_round(self):
        """record_round_metrics works even without an active round."""
        recorder = Recorder(run_id="test_009")
        recorder.record_round_metrics(total_harvest=10.0)
        output = recorder.get_output()
        assert len(output["metrics"]["by_round"]) == 1
        assert output["metrics"]["by_round"][0]["total_harvest"] == 10.0


class TestPersonalLogOutput:
    """Personal logs in recorder output."""

    def test_personal_log_in_output(self):
        """get_output() contains 'personal_logs' key with per-agent log entries."""
        config = load_config({
            "simulation": {"num_rounds": 1, "turns_per_phase": 1},
            "agents": {"names": ["Alice", "Bob"], "starting_resources": 50.0},
            "resources": {"carrying_capacity": 100.0, "regeneration_factor": 1.5},
            "leader": {"fine_destination": "common_pool"},
            "election": {"method": "plurality", "elections_every_round": False},
        })
        stub = StubLLM([
            {"action": "pass", "reasoning": "."},
            {"action": "pass", "reasoning": "."},
            {"action": "fish", "amount": 5.0, "reasoning": "."},
            {"action": "fish", "amount": 5.0, "reasoning": "."},
            {"action": "pass", "reasoning": "."},
            {"action": "pass", "reasoning": "."},
        ])
        engine = Engine(config, llm=stub, seed=42)
        engine.run()

        output = engine.get_output()
        assert "personal_logs" in output, "Output missing personal_logs"
        logs = output["personal_logs"]
        assert isinstance(logs, dict)
        assert "alice" in logs, "Missing Alice's personal log"
        assert "bob" in logs, "Missing Bob's personal log"
        assert len(logs["alice"]) > 0, "Alice's personal log is empty"
        assert len(logs["bob"]) > 0, "Bob's personal log is empty"
        # Check that entries have the expected structure
        for log_entry in logs["alice"]:
            assert "type" in log_entry
            assert "data" in log_entry
            assert "round" in log_entry


class TestChannelStates:
    """Channel state snapshot in recorder output."""

    def test_channel_states_in_output(self):
        """Channel states appear in each phase output."""
        config = load_config({
            "simulation": {"num_rounds": 1, "turns_per_phase": 1},
            "agents": {"names": ["Alice", "Bob"], "starting_resources": 50.0},
            "resources": {"carrying_capacity": 100.0, "regeneration_factor": 1.5},
            "leader": {"fine_destination": "common_pool"},
            "election": {"method": "plurality", "elections_every_round": False},
        })
        stub = StubLLM([
            {"action": "pass", "reasoning": "."},  # Alice free
            {"action": "pass", "reasoning": "."},  # Bob free
            {"action": "fish", "amount": 5.0, "reasoning": "."},  # Alice harvest
            {"action": "fish", "amount": 5.0, "reasoning": "."},  # Bob harvest
            {"action": "pass", "reasoning": "."},  # Alice post
            {"action": "pass", "reasoning": "."},  # Bob post
        ])
        engine = Engine(config, llm=stub, seed=42)
        engine.run()

        output = engine.get_output()
        for phase in output["rounds"][0]["phases"]:
            assert "channel_states" in phase, \
                f"Phase {phase['phase']} missing channel_states"
            ch_states = phase["channel_states"]
            assert isinstance(ch_states, dict)
            # All agents should be in 'public' by default
            assert "public" in ch_states
            assert len(ch_states["public"]) == 2
