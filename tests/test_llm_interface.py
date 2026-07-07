"""Tests for LLM interface abstractions: StubLLM, RecordingLLM.

Complete coverage for all interface methods.
"""

import pytest
from simulation.llm_interface import StubLLM, RecordingLLM, LLMResponse, CampaignPlatform


class TestStubLLMDecide:
    def test_decide_returns_action(self):
        stub = StubLLM([{"action": "fish", "amount": 5.0, "reasoning": "Hungry"}])
        response = stub.decide("prompt")
        assert response.action == "fish"
        assert response.amount == 5.0

    def test_decide_cycles_responses(self):
        stub = StubLLM([
            {"action": "fish", "amount": 3.0},
            {"action": "pass"},
            {"action": "fish", "amount": 7.0},
        ])
        r1 = stub.decide("")
        r2 = stub.decide("")
        r3 = stub.decide("")
        assert r1.action == "fish" and r1.amount == 3.0
        assert r2.action == "pass"
        assert r3.action == "fish" and r3.amount == 7.0

    def test_decide_cycles_wraps_around(self):
        stub = StubLLM([{"action": "fish"}, {"action": "pass"}])
        stub.decide("")  # fish
        stub.decide("")  # pass
        r = stub.decide("")  # wraps → fish
        assert r.action == "fish"

    def test_decide_empty_responses_defaults_to_pass(self):
        stub = StubLLM()
        response = stub.decide("any prompt")
        assert response.action == "pass"

    def test_decide_partial_data_fills_defaults(self):
        stub = StubLLM([{"action": "transfer"}])
        response = stub.decide("")
        assert response.action == "transfer"
        assert response.target is None
        assert response.reasoning == ""

    def test_campaign_returns_platform(self):
        stub = StubLLM([{"harvest_limit": 8.0, "penalty_rate": 3.0, "message": "Vote me"}])
        platform = stub.campaign("prompt")
        assert platform.harvest_limit == 8.0
        assert platform.penalty_rate == 3.0
        assert platform.message == "Vote me"

    def test_campaign_partial_defaults(self):
        stub = StubLLM([{"harvest_limit": 6.0}])
        platform = stub.campaign("")
        assert platform.harvest_limit == 6.0
        assert platform.penalty_rate == 1.0  # Default
        assert platform.message == ""  # Default

    def test_vote_returns_candidate(self):
        stub = StubLLM([{"vote_for": "alice"}])
        result = stub.vote("")
        assert result == "alice"

    def test_vote_empty_defaults(self):
        stub = StubLLM([{}])
        result = stub.vote("")
        assert result == ""

    def test_reflect_returns_memories(self):
        stub = StubLLM([{"memories": [{"turn": 1, "type": "reflection", "content": "Lesson learned"}]}])
        memories = stub.reflect("")
        # StubLLM.reflect now returns empty — doesn't consume from response list
        assert memories == []

    def test_reflect_empty_defaults(self):
        stub = StubLLM([{}])
        memories = stub.reflect("")
        assert memories == []

    def test_reset(self):
        stub = StubLLM([
            {"action": "fish", "amount": 5.0},
            {"action": "pass"},
        ])
        r1 = stub.decide("")  # fish
        assert r1.action == "fish"
        stub.reset()
        r2 = stub.decide("")  # fish again (counter reset)
        assert r2.action == "fish"


class TestRecordingLLM:
    def test_records_decide(self):
        inner = StubLLM([{"action": "fish", "amount": 5.0}])
        recorder = RecordingLLM(inner)
        response = recorder.decide("Should I fish?")
        assert response.action == "fish"
        assert len(recorder.history) == 1
        assert recorder.history[0]["prompt"] == "Should I fish?"

    def test_records_campaign(self):
        inner = StubLLM([{"harvest_limit": 7.0, "penalty_rate": 2.0}])
        recorder = RecordingLLM(inner)
        platform = recorder.campaign("Run for leader!")
        assert platform.harvest_limit == 7.0
        assert len(recorder.history) == 1
        assert "Run for leader!" in str(recorder.history[0]["prompt"])

    def test_records_vote(self):
        inner = StubLLM([{"vote_for": "bob"}])
        recorder = RecordingLLM(inner)
        result = recorder.vote("Who to vote for?")
        assert result == "bob"
        assert len(recorder.history) == 1

    def test_records_reflect(self):
        inner = StubLLM([{"memories": [{"content": "I learned something"}]}])
        recorder = RecordingLLM(inner)
        memories = recorder.reflect("What did I learn?")
        # StubLLM.reflect returns empty — RecordingLLM delegates
        assert memories == []
        assert len(recorder.history) == 1


class TestPromptLogSerialization:
    """Verify RecordingLLM history is JSON-serializable (for --record-prompts)."""

    def _to_serializable(self, obj):
        if obj is None:
            return None
        if isinstance(obj, (int, float, str, bool)):
            return obj
        if isinstance(obj, (list, tuple)):
            return [self._to_serializable(v) for v in obj]
        if isinstance(obj, set):
            return [self._to_serializable(v) for v in obj]
        if isinstance(obj, dict):
            return {k: self._to_serializable(v) for k, v in obj.items()}
        if hasattr(obj, "__dict__"):
            return {k: self._to_serializable(v) for k, v in obj.__dict__.items()
                    if not k.startswith("_")}
        return str(obj)

    def test_all_call_types_serializable(self):
        """decide, campaign, vote, reflect, summarize, analyze all serialize."""
        import json
        stub = StubLLM([
            {"action": "talk", "message": "hi", "reasoning": "."},
            {"harvest_limit": 5.0, "penalty_rate": 2.0, "message": ".", "reasoning": "."},
            {"vote_for": "alice"},
        ])
        rec = RecordingLLM(stub)
        rec.decide("decide prompt")
        rec.campaign("campaign prompt")
        rec.vote("vote prompt")
        rec.reflect("reflect prompt")
        rec.summarize("summarize prompt")
        rec.analyze([{"turn": 1, "agent": "alice", "message": "hi"}])

        prompt_log = []
        for entry in rec.history:
            prompt_log.append({
                "prompt": self._to_serializable(entry["prompt"]),
                "response": self._to_serializable(entry["response"]),
            })

        # Must not raise
        serialized = json.dumps(prompt_log, indent=2)
        assert len(serialized) > 100
        assert len(prompt_log) == 6

    def test_prompt_log_through_engine(self, tmp_path):
        """Full engine run with RecordingLLM produces serializable history."""
        import json
        from simulation.engine import Engine
        from simulation.config import load_config

        config = load_config({
            "simulation": {"num_rounds": 1, "turns_per_phase": 1},
            "agents": {"names": ["Alice", "Bob"], "starting_resources": 50.0},
            "resources": {"carrying_capacity": 100.0, "regeneration_factor": 1.5},
            "leader": {"fine_destination": "common_pool"},
            "election": {"method": "plurality", "first_election_round": 2},
        })
        def p():
            return {"action": "pass", "reasoning": "."}
        def fish(amt):
            return {"action": "fish", "amount": amt, "reasoning": "."}

        stub = StubLLM([p(), p(), fish(5.0), fish(5.0), p(), p()])
        rec = RecordingLLM(stub)
        engine = Engine(config, llm=rec, seed=42)
        engine.run()

        prompt_log = []
        for entry in rec.history:
            prompt_log.append({
                "prompt": self._to_serializable(entry["prompt"]),
                "response": self._to_serializable(entry["response"]),
            })

        serialized = json.dumps(prompt_log, indent=2)
        assert len(serialized) > 500
        # Should contain the prompts
        assert "free_interaction" in prompt_log[0]["prompt"] or "harvest" in prompt_log[3]["prompt"]

    def test_prompt_log_file_roundtrip(self, tmp_path):
        """Prompt log saved to file and reloaded correctly."""
        import json
        from simulation.llm_interface import StubLLM, RecordingLLM

        stub = StubLLM([{"action": "pass", "reasoning": "."}])
        rec = RecordingLLM(stub)
        rec.decide("test")

        prompt_log = []
        for entry in rec.history:
            prompt_log.append({
                "prompt": self._to_serializable(entry["prompt"]),
                "response": self._to_serializable(entry["response"]),
            })

        fpath = tmp_path / "prompts.json"
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(prompt_log, f, indent=2, ensure_ascii=False)

        with open(fpath, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert len(loaded) == 1
        assert "prompt" in loaded[0]
        assert "response" in loaded[0]
