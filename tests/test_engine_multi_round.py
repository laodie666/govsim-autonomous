"""Phase 10: Multi-round state persistence, leader transitions, and output fidelity.

Tests 39-44 — all use StubLLM for deterministic execution.
"""

import pytest
from simulation.engine import Engine
from simulation.llm_interface import StubLLM
from simulation.config import load_config


# ─── helpers ────────────────────────────────────────────────────────

def stub(*response_dicts):
    return StubLLM(list(response_dicts))

def p():
    return {"action": "pass", "reasoning": ".", "significance": None}

def talk(target, msg="hello"):
    return {"action": "public_talk", "target": target, "message": msg,
            "reasoning": ".", "significance": "small_talk"}

def private_talk(target, msg="secret"):
    return {"action": "private_talk", "target": target, "message": msg,
            "reasoning": ".", "significance": "private"}

def fish(amt):
    return {"action": "fish", "amount": amt, "reasoning": ".", "significance": "economic"}

def vote(candidate_id):
    return {"vote_for": candidate_id}

def campaign(limit=6.0, rate=2.0):
    return {"harvest_limit": limit, "penalty_rate": rate,
            "message": f"limit={limit} rate={rate}", "reasoning": "."}


@pytest.fixture
def cfg_3r():
    """3 rounds, 3 agents, election from round 2."""
    return load_config({
        "simulation": {"num_rounds": 3, "turns_per_phase": 2},
        "agents": {"names": ["Alice", "Bob", "Charlie"], "starting_resources": 50.0},
        "resources": {"carrying_capacity": 100.0, "regeneration_factor": 1.5},
        "leader": {"fine_destination": "common_pool"},
        "election": {"method": "plurality", "first_election_round": 2},
    })


# ═════════════════════════════════════════════════════════════════════
# Test 39 —  state carries between rounds
# ═════════════════════════════════════════════════════════════════════

class TestMultiRoundState:

    def test_resources_persist_across_rounds(self, cfg_3r):
        """Test 39: Resources from Round 1 harvest carry into Round 2."""
        # Round 1: 3 agents fish 5 each.  Pool: 100→85.  Resources: 50→55 each.
        # Rounds 2+3: election with candidacy cost (5 fish per candidate per round).
        responses = (
            # R1 free (6 passes), R1 harvest (3 fish),
            # R1 post (6 passes)
            [p() for _ in range(6)] +
            [fish(5.0), fish(5.0), fish(5.0)] +
            [p() for _ in range(6)] +
            # R2 free (6 passes)
            [p() for _ in range(6)] +
            # R2 election — 3 campaigns + 3 votes
            [campaign(limit=6, rate=2) for _ in range(3)] +
            [vote("alice"), vote("alice"), vote("alice")] +
            # R2 harvest (3 fish), R2 post (6 passes)
            [fish(3.0), fish(3.0), fish(3.0)] +
            [p() for _ in range(6)] +
            # R3 free (6 passes), R3 election+harvest+post
            [p() for _ in range(6)] +
            [campaign(limit=5, rate=1) for _ in range(3)] +
            [vote("alice"), vote("alice"), vote("alice")] +
            [fish(2.0), fish(2.0), fish(2.0)] +
            [p() for _ in range(6)]
        )
        engine = Engine(cfg_3r, llm=stub(*responses), seed=42)
        engine.run()

        alice = engine.get_agent("alice")
        # R1: 50+5=55,  R2: 55-5(cost)+3=53,  R3: 53-5(cost)+2=50
        assert alice.resources == 50.0, f"Alice resources: {alice.resources}"
        assert engine.get_agent("bob").resources == 50.0
        assert engine.get_agent("charlie").resources == 50.0


    def test_leader_persists_when_no_new_election(self):
        """When elections_every_round=False, no election runs and leader stays None."""
        from simulation.llm_interface import StubLLM
        from simulation.engine import Engine
        cfg = load_config({
            "simulation": {"num_rounds": 2, "turns_per_phase": 1},
            "agents": {"names": ["Alice", "Bob"], "starting_resources": 50.0},
            "resources": {"carrying_capacity": 100.0, "regeneration_factor": 1.5},
            "leader": {"fine_destination": "common_pool", "default_limit": 10.0, "default_penalty_rate": 0.5},
            "election": {"method": "plurality", "elections_every_round": False},
        })
        def p():
            return {"action": "pass", "reasoning": "."}
        def fish(amt):
            return {"action": "fish", "amount": amt, "reasoning": "."}
        # R1: free(2), no election (False), harvest(2), post(2)
        # R2: free(2), no election (False), harvest(2), post(2)
        r1 = [p() for _ in range(2)] + [fish(5.0) for _ in range(2)] + [p() for _ in range(2)]
        r2 = [p() for _ in range(2)] + [fish(5.0) for _ in range(2)] + [p() for _ in range(2)]
        stub = StubLLM(r1 + r2)
        engine = Engine(cfg, llm=stub, seed=42)
        engine.run()
        # No leader since no election ever ran
        assert engine.leader is None, f"Expected no leader, got {engine.leader}"
        # No limit set when there's no election
        assert engine.leader_limit is None, f"Expected no leader_limit, got {engine.leader_limit}"

    def test_state_progression_3_rounds(self, cfg_3r):
        """Test 39b: Full 3-round pipeline, all phases present per round."""
        responses = (
            # R1: free(6) + harvest(3) + post(6)
            [p() for _ in range(6)] + [fish(5.0) for _ in range(3)] + [p() for _ in range(6)] +
            # R2: free(6) + campaign(3) + vote(3) + harvest(3) + post(6)
            [p() for _ in range(6)] +
            [campaign() for _ in range(3)] + [vote("alice") for _ in range(3)] +
            [fish(5.0) for _ in range(3)] + [p() for _ in range(6)] +
            # R3: free(6) + campaign(3) + vote(3) + harvest(3) + post(6)
            [p() for _ in range(6)] +
            [campaign() for _ in range(3)] + [vote("alice") for _ in range(3)] +
            [fish(5.0) for _ in range(3)] + [p() for _ in range(6)]
        )
        engine = Engine(cfg_3r, llm=stub(*responses), seed=42)
        engine.run()

        output = engine.get_output()
        assert len(output["rounds"]) == 3
        for rnd in output["rounds"]:
            phases = [p["phase"] for p in rnd["phases"]]
            if rnd["round"] == 1:
                assert phases == ["free_interaction", "harvesting", "free_interaction"]
            else:
                assert phases == ["free_interaction", "election", "harvesting", "free_interaction"]


# ═════════════════════════════════════════════════════════════════════
# Test 40 —  leader transitions
# ═════════════════════════════════════════════════════════════════════

class TestLeaderTransitions:

    def test_leader_dethroned_by_new_winner(self, cfg_3r):
        """Test 40: Alice wins R2, Bob wins R3 → Bob is leader after R3."""
        responses = (
            # R1
            [p() for _ in range(6)] + [fish(5.0) for _ in range(3)] + [p() for _ in range(6)] +
            # R2 election — Alice wins
            [p() for _ in range(6)] +
            [campaign() for _ in range(3)] + [vote("alice") for _ in range(3)] +
            [fish(5.0) for _ in range(3)] + [p() for _ in range(6)] +
            # R3 election — Bob wins
            [p() for _ in range(6)] +
            [campaign() for _ in range(3)] + [vote("bob") for _ in range(3)] +
            [fish(5.0) for _ in range(3)] + [p() for _ in range(6)]
        )
        engine = Engine(cfg_3r, llm=stub(*responses), seed=42)
        engine.run()

        assert engine.leader is not None
        assert engine.leader.id == "bob"
        # Alice was leader, now she isn't
        alice = engine.get_agent("alice")
        assert alice.is_leader is False

    def test_leader_can_be_re_elected(self, cfg_3r):
        """Alice wins both R2 and R3 → stays leader the whole time."""
        responses = (
            [p() for _ in range(6)] + [fish(5.0) for _ in range(3)] + [p() for _ in range(6)] +
            [p() for _ in range(6)] +
            [campaign() for _ in range(3)] + [vote("alice") for _ in range(3)] +
            [fish(5.0) for _ in range(3)] + [p() for _ in range(6)] +
            [p() for _ in range(6)] +
            [campaign() for _ in range(3)] + [vote("alice") for _ in range(3)] +
            [fish(5.0) for _ in range(3)] + [p() for _ in range(6)]
        )
        engine = Engine(cfg_3r, llm=stub(*responses), seed=42)
        engine.run()

        assert engine.leader.id == "alice"

    def test_leader_changes_limit_and_rate(self, cfg_3r):
        """Each new leader's platform (limit+rate) replaces the old one."""
        # R2: Alice wins with limit=6, rate=2
        # R3: Bob wins with limit=10, rate=0
        responses = (
            [p() for _ in range(6)] + [fish(5.0) for _ in range(3)] + [p() for _ in range(6)] +
            [p() for _ in range(6)] +
            [campaign(limit=6, rate=2), campaign(limit=7, rate=1), campaign(limit=5, rate=3)] +
            [vote("alice"), vote("alice"), vote("alice")] +
            [fish(5.0) for _ in range(3)] + [p() for _ in range(6)] +
            [p() for _ in range(6)] +
            [campaign(limit=6, rate=2), campaign(limit=10, rate=0), campaign(limit=5, rate=3)] +
            [vote("bob"), vote("bob"), vote("bob")] +
            [fish(5.0) for _ in range(3)] + [p() for _ in range(6)]
        )
        engine = Engine(cfg_3r, llm=stub(*responses), seed=42)
        engine.run()

        assert engine.leader_limit == 10.0
        assert engine.leader_penalty_rate == 0.0


# ═════════════════════════════════════════════════════════════════════
# Test 41 —  private group DM
# ═════════════════════════════════════════════════════════════════════

class TestGroupDMs:

    def test_private_group_dm_recorded(self, cfg_3r):
        """Test 41: Agent targets 2+ agents in private_talk → recorded as group."""
        llm = stub(
            # R1 free interaction — Alice sends a group DM to Bob and Charlie
            {"action": "private_talk", "target": None, "targets": ["bob", "charlie"],
             "message": "Let's form an alliance", "reasoning": ".", "significance": "alliance"},
            p(), p(), p(), p(), p(),  # remaining turns pass
            *[fish(5.0) for _ in range(3)],
            *[p() for _ in range(6)],
            # R2
            *[p() for _ in range(6)],
            *[campaign() for _ in range(3)],
            *[vote("alice") for _ in range(3)],
            *[fish(3.0) for _ in range(3)],
            *[p() for _ in range(6)],
            # R3
            *[p() for _ in range(6)],
            *[campaign() for _ in range(3)],
            *[vote("alice") for _ in range(3)],
            *[fish(2.0) for _ in range(3)],
            *[p() for _ in range(6)],
        )
        engine = Engine(cfg_3r, llm=llm, seed=42)
        engine.run()

        output = engine.get_output()
        r1_free = output["rounds"][0]["phases"][0]
        first_event = r1_free["turns"][0]

        assert first_event["action"] == "private_talk"
        assert first_event["targets"] == ["bob", "charlie"]
        assert first_event["is_private"] is True
        assert first_event["message"] == "Let's form an alliance"


# ═════════════════════════════════════════════════════════════════════
# Test 42 —  public talk visibility (message in output)
# ═════════════════════════════════════════════════════════════════════

class TestTalkVisibility:

    def test_public_talk_message_in_output(self, cfg_3r):
        """Test 42: Public talk event has agent, message, target in output."""
        responses = (
            talk("bob", "Hello everyone!"),
            *[p() for _ in range(5)],
            *[fish(5.0) for _ in range(3)],
            *[p() for _ in range(6)],
            *[p() for _ in range(6)],
            *[campaign() for _ in range(3)],
            *[vote("alice") for _ in range(3)],
            *[fish(3.0) for _ in range(3)],
            *[p() for _ in range(6)],
            *[p() for _ in range(6)],
            *[campaign() for _ in range(3)],
            *[vote("alice") for _ in range(3)],
            *[fish(2.0) for _ in range(3)],
            *[p() for _ in range(6)],
        )
        engine = Engine(cfg_3r, llm=stub(*responses), seed=42)
        engine.run()

        output = engine.get_output()
        r1_free = output["rounds"][0]["phases"][0]

        # Find the public_talk event (turn order is shuffled)
        talk_events = [e for e in r1_free["turns"] if e["action"] == "public_talk"]
        assert len(talk_events) == 1
        talk_event = talk_events[0]

        assert talk_event["target"] == "bob"
        assert talk_event["message"] == "Hello everyone!"
        assert talk_event["is_private"] is False

    def test_private_talk_is_private(self, cfg_3r):
        """Test 43: Private talk event has is_private=True."""
        responses = (
            private_talk("bob", "This is between us"),
            *[p() for _ in range(5)],
            *[fish(5.0) for _ in range(3)],
            *[p() for _ in range(6)],
            *[p() for _ in range(6)],
            *[campaign() for _ in range(3)],
            *[vote("alice") for _ in range(3)],
            *[fish(3.0) for _ in range(3)],
            *[p() for _ in range(6)],
            *[p() for _ in range(6)],
            *[campaign() for _ in range(3)],
            *[vote("alice") for _ in range(3)],
            *[fish(2.0) for _ in range(3)],
            *[p() for _ in range(6)],
        )
        engine = Engine(cfg_3r, llm=stub(*responses), seed=42)
        engine.run()

        output = engine.get_output()
        r1_free = output["rounds"][0]["phases"][0]

        talk_events = [e for e in r1_free["turns"] if e["action"] == "private_talk"]
        assert len(talk_events) == 1
        talk_event = talk_events[0]

        assert talk_event["target"] == "bob"
        assert talk_event["is_private"] is True


# ═════════════════════════════════════════════════════════════════════
# Test 44 —  significance tagging
# ═════════════════════════════════════════════════════════════════════

class TestSignificance:

    def test_significance_in_output(self, cfg_3r):
        """Test 44: Agent action significance appears in the output."""
        responses = (
            {"action": "public_talk", "target": "bob", "message": "You owe me",
             "reasoning": ".", "significance": "collusion"},
            *[p() for _ in range(5)],
            *[fish(5.0) for _ in range(3)],
            *[p() for _ in range(6)],
            *[p() for _ in range(6)],
            *[campaign() for _ in range(3)],
            *[vote("alice") for _ in range(3)],
            *[fish(3.0) for _ in range(3)],
            *[p() for _ in range(6)],
            *[p() for _ in range(6)],
            *[campaign() for _ in range(3)],
            *[vote("alice") for _ in range(3)],
            *[fish(2.0) for _ in range(3)],
            *[p() for _ in range(6)],
        )
        engine = Engine(cfg_3r, llm=stub(*responses), seed=42)
        engine.run()

        output = engine.get_output()
        r1_free = output["rounds"][0]["phases"][0]
        first_event = r1_free["turns"][0]

        assert first_event["action"] == "public_talk"
        # Significance is no longer self-assessed — it's set by post-hoc LLM analysis
        # StubLLM.analyze returns empty, so event significance is None
        assert first_event.get("significance") is None
