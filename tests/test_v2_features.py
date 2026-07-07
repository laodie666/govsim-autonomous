"""Integration tests for v2 features: heard_by, transfer null, group field, dissolution, reflection, candidacy cost.

Each test is committed independently per spec.
"""

from simulation.engine import Engine
from simulation.config import load_config
from simulation.llm_interface import StubLLM


# ─── helpers ────────────────────────────────────────────────────────

def p():
    return {"action": "pass", "reasoning": "."}

def fish(amt):
    return {"action": "fish", "amount": amt, "reasoning": "."}

def campaign(limit=5.0, rate=2.0):
    return {"harvest_limit": limit, "penalty_rate": rate, "message": ".", "reasoning": "."}

def vote(candidate):
    return {"vote_for": candidate}


# ═══════════════════════════════════════════════════════════════════
# Test 1 — heard_by validation
# ═══════════════════════════════════════════════════════════════════

def test_heard_by_private_channel_members_only():
    """Private channel messages have heard_by set to only channel members."""
    config = load_config({
        "simulation": {"num_rounds": 1, "turns_per_phase": 1},
        "agents": {"names": ["Alice", "Bob", "Charlie"], "starting_resources": 50.0},
        "resources": {"carrying_capacity": 100.0, "regeneration_factor": 1.5},
        "leader": {"fine_destination": "common_pool"},
        "election": {"method": "plurality", "first_election_round": 2},
    })
    engine = Engine(config, llm=StubLLM(), seed=42)
    alice = engine.agents["alice"]
    bob = engine.agents["bob"]
    charlie = engine.agents["charlie"]

    # Put Alice and Bob in a private channel
    channel_name = engine.channels._generate_channel_name()
    engine.channels._channels[channel_name] = {"alice", "bob"}
    engine.channels._agent_channel["alice"] = channel_name
    engine.channels._agent_channel["bob"] = channel_name

    # Alice talks in her channel
    engine.llm = StubLLM(responses=[
        {"action": "talk", "message": "secret meeting", "reasoning": "."},
    ])
    engine.recorder.start_round(1)
    engine.recorder.start_phase("free_interaction")
    engine.current_round = 1
    engine.turn_counter = 5
    engine.current_phase = "free_interaction"
    engine._handle_agent_turn(alice)

    # Check the recorder event's heard_by
    output = engine.get_output()
    phase = output["rounds"][0]["phases"][0]
    talk_events = [e for e in phase["turns"] if e.get("message") == "secret meeting"]
    assert len(talk_events) == 1, "Should have one talk event"
    heard_by = talk_events[0].get("heard_by", [])
    assert heard_by is not None, "heard_by should not be None"
    heard_set = set(heard_by)
    assert "alice" in heard_set, "Alice should hear her own message"
    assert "bob" in heard_set, "Bob should hear the message"
    assert "charlie" not in heard_set, "Charlie should not hear private message"


# ═══════════════════════════════════════════════════════════════════
# Test 2 — Transfer null target
# ═══════════════════════════════════════════════════════════════════

def test_transfer_null_target_records_failure():
    """Transfer with target=None records a failure in sender's personal log."""
    config = load_config({
        "simulation": {"num_rounds": 1, "turns_per_phase": 1},
        "agents": {"names": ["Alice", "Bob"], "starting_resources": 50.0},
        "resources": {"carrying_capacity": 100.0, "regeneration_factor": 1.5},
        "leader": {"fine_destination": "common_pool"},
        "election": {"method": "plurality", "first_election_round": 2},
    })
    # Alice sends transfer with target=None (invalid). Bob does pass.
    stub = StubLLM([
        {"action": "transfer", "target": None, "amount": 10.0, "reasoning": "."},
        p(),
        # harvest
        fish(5.0), fish(5.0),
        # post
        p(), p(),
    ])
    engine = Engine(config, llm=stub, seed=42)
    engine.run()

    alice = engine.get_agent("alice")
    # When target is None, execute_transfer returns early without a transfer_sent entry
    transfer_sent = [e for e in alice.personal_log if e["type"] == "transfer_sent"]
    assert len(transfer_sent) == 0, \
        "Alice should have no transfer_sent entry when target is None"
    # Alice's resources should remain unchanged (no transfer deducted)
    # She caught 5 fish in harvest, so 50 + 5 = 55
    assert alice.resources == 55.0, \
        f"Alice's resources should be 55.0, got {alice.resources}"


# ═══════════════════════════════════════════════════════════════════
# Test 3 — Group field fix
# ═══════════════════════════════════════════════════════════════════

def test_llm_response_group_field_parsed():
    """LLMResponse.group is correctly parsed from the LLM response."""
    from simulation.llm_client import _extract_json
    from simulation.llm_interface import LLMResponse
    data = _extract_json('{"action": "talk", "group": "#secret_0", "message": "hi", "reasoning": "."}')
    resp = LLMResponse(
        action=data.get("action", "pass"),
        target=data.get("target"),
        targets=data.get("targets"),
        message=data.get("message"),
        amount=data.get("amount"),
        group=data.get("group"),
        reasoning=data.get("reasoning", ""),
    )
    assert resp.group == "#secret_0", f"Expected group='#secret_0', got '{resp.group}'"
    assert resp.action == "talk"
    assert resp.message == "hi"


# ═══════════════════════════════════════════════════════════════════
# Test 4 — Per-phase channel dissolution
# ═══════════════════════════════════════════════════════════════════

def test_per_phase_channel_dissolution():
    """After a phase transition via engine.run(), all agents are in 'public'."""
    config = load_config({
        "simulation": {"num_rounds": 1, "turns_per_phase": 1},
        "agents": {"names": ["Alice", "Bob"], "starting_resources": 50.0},
        "resources": {"carrying_capacity": 100.0, "regeneration_factor": 1.5},
        "leader": {"fine_destination": "common_pool"},
        "election": {"method": "plurality", "elections_every_round": False},
    })
    stub = StubLLM([
        {"action": "create_group", "targets": ["bob"], "reasoning": "."},
        {"action": "pass", "reasoning": "."},
        fish(5.0), fish(5.0),
        p(), p(),
    ])
    engine = Engine(config, llm=stub, seed=42)
    engine.run()
    # After full run, all agents should be in 'public'
    for aid in engine.agents:
        assert engine.channels.agent_channel(aid) == "public", \
            f"{aid} should be in public after run, got {engine.channels.agent_channel(aid)}"


# ═══════════════════════════════════════════════════════════════════
# Test 5 — Reflection phase output
# ═══════════════════════════════════════════════════════════════════

class ReflectingStub(StubLLM):
    """StubLLM that returns reflection content when reflect() is called."""
    def reflect(self, prompt: str) -> list[dict]:
        return [{
            "content": "I caught 5 fish this round. I plan to cooperate next round.",
            "significance": "personal",
            "emotional_impact": "neutral",
        }]

def test_reflection_phase_output():
    """Each agent has at least one 'reflection' type Memory after running engine."""
    config = load_config({
        "simulation": {"num_rounds": 1, "turns_per_phase": 1},
        "agents": {"names": ["Alice", "Bob"], "starting_resources": 50.0},
        "resources": {"carrying_capacity": 100.0, "regeneration_factor": 1.5},
        "leader": {"fine_destination": "common_pool"},
        "election": {"method": "plurality", "elections_every_round": True},
    })
    responses = [p() for _ in range(2)] + [campaign() for _ in range(2)] + [vote("alice") for _ in range(2)] + [fish(5.0) for _ in range(2)] + [p() for _ in range(2)]
    stub = ReflectingStub(responses)
    engine = Engine(config, llm=stub, seed=42)
    engine.run()
    for agent in engine.agent_list:
        reflections = [m for m in agent.memories if m.type == "reflection"]
        assert len(reflections) >= 1, f"{agent.name} has no reflection memories"
        assert reflections[0].content, f"{agent.name} has empty reflection content"
        assert "fish" in reflections[0].content.lower(), \
            f"{agent.name} reflection should mention fish, got: {reflections[0].content}"


# ═══════════════════════════════════════════════════════════════════
# Test 6 — Candidacy cost
# ═══════════════════════════════════════════════════════════════════

def test_candidacy_cost_deducted_and_penniless_skip():
    """Running for leader deducts 5 fish; agents with < 5 cannot run."""
    config = load_config({
        "simulation": {"num_rounds": 1, "turns_per_phase": 1},
        "agents": {"names": ["Alice", "Bob"], "starting_resources": 50.0},
        "resources": {"carrying_capacity": 100.0, "regeneration_factor": 1.5},
        "leader": {"fine_destination": "common_pool", "default_limit": 10.0, "default_penalty_rate": 0.5, "candidacy_cost": 5.0},
        "election": {"method": "plurality", "elections_every_round": True},
    })
    # Free(2), campaign(1 - only Alice), vote(2), harvest(2), post(2) = 9
    responses = [p() for _ in range(2)] + [campaign()] + [vote("alice") for _ in range(2)] + [fish(5.0) for _ in range(2)] + [p() for _ in range(2)]
    stub = StubLLM(responses)
    engine = Engine(config, llm=stub, seed=42)
    # Give Bob only 3 fish so he can't afford candidacy
    engine.get_agent("bob").resources = 3.0
    engine.run()

    alice = engine.get_agent("alice")
    bob = engine.get_agent("bob")

    # Alice was a candidate (could afford 5 fish) and won
    # Alice started with 50, paid 5 candidacy, caught 5 fish = 50
    assert engine.leader is not None, "Alice should be leader"
    assert engine.leader.id == "alice", "Alice should win election"
    assert alice.resources == 50.0, \
        f"Alice should have 50.0 (50 start - 5 cost + 5 harvest), got {alice.resources}"

    # Bob was NOT a candidate (had 3 fish, could not afford 5 fish cost)
    # Bob had 3, did not pay candidacy, caught 5 fish = 8
    assert bob.resources == 8.0, \
        f"Bob should have 8.0 (3 start + 5 harvest, no candidacy), got {bob.resources}"
