"""Engine integration tests with StubLLM.

Phase 7-10: Tests 27-44 from the specification.
All tests use StubLLM for deterministic, LLM-free execution.
"""

import pytest
from simulation.engine import Engine
from simulation.llm_interface import StubLLM
from simulation.config import load_config


def make_stub_responses(*response_dicts):
    """Helper to create a StubLLM with the given responses."""
    return StubLLM(list(response_dicts))


def pass_response():
    return {"action": "pass", "reasoning": "Nothing to do", "significance": "small_talk"}


def talk_response(target, message, significance="small_talk"):
    return {
        "action": "public_talk",
        "target": target,
        "message": message,
        "reasoning": "Speaking my mind",
        "significance": significance,
    }


def vote_response(candidate_id):
    return {"vote_for": candidate_id}


def campaign_response(limit=6.0, rate=2.0):
    return {
        "harvest_limit": limit,
        "penalty_rate": rate,
        "message": f"Vote for me! Limit: {limit}, Penalty: {rate}",
        "reasoning": "This is fair",
    }


def fish_response(amount=5.0, significance="economic"):
    return {
        "action": "fish", "amount": amount,
        "reasoning": "Need fish", "significance": significance,
    }


def transfer_response(target, amount):
    return {
        "action": "transfer",
        "target": target,
        "amount": amount,
        "reasoning": "Sharing",
        "significance": "economic",
    }


class TestGini:
    """Unit tests for Gini coefficient calculation."""

    def test_gini_perfect_equality(self):
        """All agents have the same resources → Gini = 0."""
        gini = Engine._calculate_gini([50.0, 50.0, 50.0, 50.0])
        assert gini == 0.0

    def test_gini_maximum_inequality(self):
        """One agent has everything → Gini approaches 1."""
        gini = Engine._calculate_gini([100.0, 0.0, 0.0, 0.0])
        assert abs(gini - 0.75) < 0.01  # n=4, gini = (4+1)/4 - 2*1/(4*100) = 1.25 - 0.005 → ~0.75

    def test_gini_empty_list(self):
        gini = Engine._calculate_gini([])
        assert gini == 0.0

    def test_gini_all_zero(self):
        """All zeros → Gini = 0 (formula avoids division by zero)."""
        gini = Engine._calculate_gini([0.0, 0.0, 0.0])
        assert gini == 0.0


@pytest.fixture
def default_config():
    return load_config({
        "simulation": {"num_rounds": 1, "turns_per_phase": 3},
        "agents": {"names": ["Alice", "Bob", "Charlie"], "starting_resources": 50.0},
        "resources": {"carrying_capacity": 100.0, "regeneration_factor": 1.5},
        "leader": {"fine_destination": "common_pool"},
        "election": {"method": "plurality", "elections_every_round": False},
    })


class TestRound1FreeInteraction:
    """Tests 27-31: Round 1 with no election."""

    def test_round_1_free_interaction_cycles(self, default_config):
        """Test 27: 3 agents, 3 turns each → 9 total events in free interaction."""
        stub = make_stub_responses(
            *[pass_response() for _ in range(9)]  # 3 agents × 3 turns
        )
        engine = Engine(default_config, llm=stub, seed=42)
        engine.run()

        output = engine.get_output()
        rounds = output["rounds"]
        assert len(rounds) == 1
        assert rounds[0]["round"] == 1

        # Phase 1 should be free_interaction
        phases = rounds[0]["phases"]
        assert len(phases) >= 1
        interaction_phase = phases[0]
        assert interaction_phase["phase"] == "free_interaction"

        # All events should be "pass" actions
        assert len(interaction_phase["turns"]) == 9

    def test_round_1_no_election(self, default_config):
        """Test 28: Round 1 has no election phase since first_election_round=2."""
        stub = make_stub_responses(
            *[pass_response() for _ in range(9)],    # Free interaction
            *[pass_response() for _ in range(9)],    # Harvest (3 fish actions)
        )

        engine = Engine(default_config, llm=stub, seed=42)
        engine.run()

        output = engine.get_output()
        phases = output["rounds"][0]["phases"]
        phase_names = [p["phase"] for p in phases]
        assert "election" not in phase_names

    def test_round_1_no_penalties(self, default_config):
        """Test 31: Round 1 has no leader → no limit → no penalties."""
        stub = make_stub_responses(
            *[pass_response() for _ in range(9)],  # Free interaction
            fish_response(8.0),  # Alice fishes 8
            fish_response(10.0),  # Bob fishes 10
            fish_response(4.0),  # Charlie fishes 4
        )

        engine = Engine(default_config, llm=stub, seed=42)
        engine.run()

        output = engine.get_output()

        # Find harvest phase
        for phase in output["rounds"][0]["phases"]:
            if phase["phase"] == "harvesting":
                for event in phase["turns"]:
                    assert event["penalty"] is None  # No penalties in round 1
                    assert event["leader_limit"] is None

    def test_round_1_completes(self, default_config):
        """Test 30: Full round completes with all 3 phases (free+harvest+free)."""
        stub = make_stub_responses(
            *[pass_response() for _ in range(9)],  # Free interaction
            *[fish_response(5.0) for _ in range(3)],  # Harvest
            *[pass_response() for _ in range(9)],  # Post-harvest interaction
        )

        engine = Engine(default_config, llm=stub, seed=42)
        engine.run()

        output = engine.get_output()
        phases = output["rounds"][0]["phases"]
        phase_names = [p["phase"] for p in phases]
        assert phase_names == ["free_interaction", "harvesting", "free_interaction"]

    def test_round_1_harvest_deducts_from_pool(self, default_config):
        """Test 29: Fishing reduces pool and increases agent resources."""
        stub = make_stub_responses(
            *[pass_response() for _ in range(9)],  # Free interaction
            fish_response(8.0),  # Alice fishes 8
            fish_response(10.0),  # Bob fishes 10
            fish_response(4.0),  # Charlie fishes 4
        )

        engine = Engine(default_config, llm=stub, seed=42)
        engine.run()

        # Total harvested = 8 + 10 + 4 = 22
        # Pool started at 100, should be 78
        # Alice: 50 + 8 = 58, Bob: 50 + 10 = 60, Charlie: 50 + 4 = 54

        pool_final = None
        for phase in engine.get_output()["rounds"][0]["phases"]:
            if phase["phase"] == "harvesting":
                last_event = phase["turns"][-1]
                pool_final = last_event["resources_after"]["pool"]

        assert pool_final == 78.0


class TestElectionAndLeader:
    """Tests 32-38: Election and leader enforcement."""

    @pytest.fixture
    def election_config(self):
        return load_config({
            "simulation": {"num_rounds": 2, "turns_per_phase": 2},
            "agents": {"names": ["Alice", "Bob", "Charlie"], "starting_resources": 50.0},
            "resources": {"carrying_capacity": 100.0, "regeneration_factor": 1.5},
            "leader": {"fine_destination": "common_pool"},
            "election": {"method": "plurality", "elections_every_round": True},
        })

    def test_election_round_2(self, election_config):
        """Test 32: Election phase runs in round 2 with candidates and voting."""
        # Round 1: free interaction + election + harvest + post-harvest
        # Round 2: free interaction + election + harvest + post-harvest
        r1_free = [pass_response() for _ in range(6)]  # 3 agents × 2 turns
        # Round 1 also has election (elections_every_round=True)
        r1_campaigns = [
            campaign_response(limit=5.0, rate=2.0),
            campaign_response(limit=7.0, rate=1.0),
            campaign_response(limit=6.0, rate=3.0),
        ]
        r1_votes = [
            vote_response("alice"),
            vote_response("alice"),
            vote_response("alice"),
        ]
        r1_fish = [fish_response(5.0) for _ in range(3)]
        r1_post = [pass_response() for _ in range(6)]

        # Campaigns for all 3 candidates
        r2_campaigns = [
            campaign_response(limit=5.0, rate=2.0),
            campaign_response(limit=7.0, rate=1.0),
            campaign_response(limit=6.0, rate=3.0),
        ]
        # Votes: all vote for Alice
        r2_votes = [
            vote_response("alice"),
            vote_response("alice"),
            vote_response("alice"),
        ]
        r2_free = [pass_response() for _ in range(6)]
        r2_fish = [fish_response(5.0) for _ in range(3)]
        r2_post = [pass_response() for _ in range(6)]

        stub = make_stub_responses(
            *(r1_free + r1_campaigns + r1_votes + r1_fish + r1_post),
            *r2_free, *r2_campaigns, *r2_votes, *r2_fish, *r2_post,
        )

        engine = Engine(election_config, llm=stub, seed=42)
        engine.run()

        output = engine.get_output()
        assert len(output["rounds"]) == 2

        # Round 2 should have an election phase
        r2_phases = [p["phase"] for p in output["rounds"][1]["phases"]]
        assert "election" in r2_phases

        # Alice should be the leader
        assert engine.leader is not None
        assert engine.leader.id == "alice"

    def test_elected_leader_platform_applied(self, election_config):
        """Test 33: Winner's limit and penalty rate are applied."""
        # All campaigns propose different platforms
        # Alice: limit=5, rate=2
        # We make Alice win

        # R1: free(6) + campaign(3) + vote(3) + harvest(3) + post(6)
        r1 = ([pass_response() for _ in range(6)]
              + [campaign_response() for _ in range(3)]
              + [vote_response("alice") for _ in range(3)]
              + [fish_response(5.0) for _ in range(3)]
              + [pass_response() for _ in range(6)])
        # R2: free(6) + campaign(3) + vote(3) + harvest(3) + post(6)
        r2_free = [pass_response() for _ in range(6)]
        r2_campaigns = [
            campaign_response(limit=5.0, rate=2.0),
            campaign_response(limit=7.0, rate=1.0),
            campaign_response(limit=6.0, rate=3.0),
        ]
        r2_votes = [vote_response("alice"), vote_response("alice"), vote_response("alice")]
        r2_fish = [fish_response(5.0) for _ in range(3)]
        r2_post = [pass_response() for _ in range(6)]

        stub = make_stub_responses(*(r1 + r2_free + r2_campaigns + r2_votes + r2_fish + r2_post))
        engine = Engine(election_config, llm=stub, seed=42)
        engine.run()

        assert engine.leader_limit == 5.0
        assert engine.leader_penalty_rate == 2.0

    def test_limit_violation_penalized(self, election_config):
        """Test 34: Agent exceeds limit → penalty applied automatically."""
        # R1: free(6) + campaign(3) + vote(3) + harvest(3) + post(6)
        r1 = ([pass_response() for _ in range(6)]
              + [campaign_response() for _ in range(3)]
              + [vote_response("alice") for _ in range(3)]
              + [fish_response(5.0) for _ in range(3)]
              + [pass_response() for _ in range(6)])
        # R2: free(6) + campaign(3) + vote(3) + harvest(3) + post(6)
        r2_free = [pass_response() for _ in range(6)]
        r2_campaigns = [
            campaign_response(limit=5.0, rate=2.0),
            campaign_response(limit=7.0, rate=1.0),
            campaign_response(limit=6.0, rate=3.0),
        ]
        r2_votes = [vote_response("alice"), vote_response("alice"), vote_response("alice")]
        # Bob exceeds limit (8 fish when limit is 5, rate is 2 → penalty = 6)
        r2_fish = [
            fish_response(4.0),   # Alice under limit
            fish_response(8.0),   # Bob exceeds!  penalty = (8-5)×2 = 6
            fish_response(3.0),   # Charlie under limit
        ]
        r2_post = [pass_response() for _ in range(6)]

        stub = make_stub_responses(*(r1 + r2_free + r2_campaigns + r2_votes + r2_fish + r2_post))
        engine = Engine(election_config, llm=stub, seed=42)
        engine.run()

        # Bob should have a violation
        bob = engine.get_agent("bob")
        assert bob.violations == 1

        # Bob should have paid a penalty (deducted from resources)
        # Bob started round 2 with regen from round 1
        # This is getting complex — let's check the output event for the penalty
        for phase in engine.get_output()["rounds"][1]["phases"]:
            if phase["phase"] == "harvesting":
                for event in phase["turns"]:
                    if event["agent"] == "bob":
                        assert event["penalty"] is not None
                        assert event["penalty"]["amount"] == 6.0
                        assert event["penalty"]["imposed_by"] == "alice"
                        break

    def test_under_limit_no_penalty(self, election_config):
        """Test 35: Fishing under limit → no penalty at all."""
        r1 = [pass_response() for _ in range(6)] + [fish_response(5.0) for _ in range(3)] + [pass_response() for _ in range(6)]
        r2_free = [pass_response() for _ in range(6)]
        r2_campaigns = [
            campaign_response(limit=5.0, rate=2.0),
            campaign_response(limit=7.0, rate=1.0),
            campaign_response(limit=6.0, rate=3.0),
        ]
        r2_votes = [vote_response("alice"), vote_response("alice"), vote_response("alice")]
        r2_fish = [
            fish_response(3.0),  # Under limit
            fish_response(4.0),  # Under limit
            fish_response(5.0),  # Exactly at limit
        ]
        r2_post = [pass_response() for _ in range(6)]

        stub = make_stub_responses(*(r1 + r2_free + r2_campaigns + r2_votes + r2_fish + r2_post))
        engine = Engine(election_config, llm=stub, seed=42)
        engine.run()

        for phase in engine.get_output()["rounds"][1]["phases"]:
            if phase["phase"] == "harvesting":
                for event in phase["turns"]:
                    assert event["penalty"] is None

    def test_output_has_all_phases(self, election_config):
        """Test 37: Output contains phase names for round 2."""
        r1 = [pass_response() for _ in range(6)] + [fish_response(5.0) for _ in range(3)] + [pass_response() for _ in range(6)]
        r2_free = [pass_response() for _ in range(6)]
        r2_campaigns = [
            campaign_response(limit=5.0, rate=2.0),
            campaign_response(limit=7.0, rate=1.0),
            campaign_response(limit=6.0, rate=3.0),
        ]
        r2_votes = [vote_response("alice"), vote_response("alice"), vote_response("alice")]
        r2_fish = [fish_response(5.0) for _ in range(3)]
        r2_post = [pass_response() for _ in range(6)]

        stub = make_stub_responses(*(r1 + r2_free + r2_campaigns + r2_votes + r2_fish + r2_post))
        engine = Engine(election_config, llm=stub, seed=42)
        engine.run()

        r2_phases = [p["phase"] for p in engine.get_output()["rounds"][1]["phases"]]
        assert r2_phases == ["free_interaction", "election", "harvesting", "free_interaction"]

    def test_candidacy_cost_deducted(self, election_config):
        """Agents who run for leader lose 5 fish (sunk cost)."""
        # All 3 agents can afford 5-fish cost (they have 50)
        r1_free = [pass_response() for _ in range(6)]
        r1_campaigns = [
            campaign_response(limit=5.0, rate=2.0),
            campaign_response(limit=7.0, rate=1.0),
            campaign_response(limit=6.0, rate=3.0),
        ]
        r1_votes = [vote_response("alice"), vote_response("alice"), vote_response("alice")]
        r1_fish = [fish_response(5.0) for _ in range(3)]
        r1_post = [pass_response() for _ in range(6)]

        r2_free = [pass_response() for _ in range(6)]
        r2_campaigns = [
            campaign_response(limit=5.0, rate=2.0),
            campaign_response(limit=7.0, rate=1.0),
            campaign_response(limit=6.0, rate=3.0),
        ]
        r2_votes = [vote_response("alice"), vote_response("alice"), vote_response("alice")]
        r2_fish = [fish_response(5.0) for _ in range(3)]
        r2_post = [pass_response() for _ in range(6)]

        stub = make_stub_responses(
            *(r1_free + r1_campaigns + r1_votes + r1_fish + r1_post),
            *(r2_free + r2_campaigns + r2_votes + r2_fish + r2_post),
        )
        engine = Engine(election_config, llm=stub, seed=42)
        engine.run()

        assert engine._election_data is not None
        assert engine._election_data["winner"] == "alice"
        # After round 1: each agent had 50 - 5 (candidacy) + 5 (fish) = 50
        # After round 2: each agent had 50 - 5 (candidacy) + 5 (fish) = 50
        # Without cost: 50 + 5 + 5 = 60
        alice = engine.get_agent("alice")
        bob = engine.get_agent("bob")
        charlie = engine.get_agent("charlie")
        # This asserts the cost IS being deducted with exact expected values
        assert alice.resources == 50.0, \
            f"Alice should have exactly 50 resources, got {alice.resources}"
        assert bob.resources == 50.0, \
            f"Bob should have exactly 50 resources, got {bob.resources}"
        assert charlie.resources == 50.0, \
            f"Charlie should have exactly 50 resources, got {charlie.resources}"

    def test_candidacy_skipped_when_penniless(self):
        """Agent with < 5 fish cannot run; fallback to default policy."""
        config = load_config({
            "simulation": {"num_rounds": 1, "turns_per_phase": 1},
            "agents": {"names": ["Alice", "Bob"], "starting_resources": 3.0},  # < 5!
            "resources": {"carrying_capacity": 100.0, "regeneration_factor": 1.5},
            "leader": {"fine_destination": "common_pool", "default_limit": 10.0, "default_penalty_rate": 0.5, "candidacy_cost": 5.0},
            "election": {"method": "plurality", "elections_every_round": True},
        })
        # free_interaction (2 passes), then election (no one can run → fallback)
        stub = StubLLM([
            {"action": "pass", "reasoning": "."},
            {"action": "pass", "reasoning": "."},
            # harvest
            {"action": "fish", "amount": 5.0, "reasoning": "."},
            {"action": "fish", "amount": 5.0, "reasoning": "."},
            # post
            {"action": "pass", "reasoning": "."},
            {"action": "pass", "reasoning": "."},
        ])
        engine = Engine(config, llm=stub, seed=42)
        engine.run()
        # No leader should be elected, but default policy applies
        assert engine.leader is None
        assert engine.leader_limit == 10.0, \
            f"Expected default limit 10.0, got {engine.leader_limit}"
        assert engine.leader_penalty_rate == 0.5, \
            f"Expected default penalty rate 0.5, got {engine.leader_penalty_rate}"
        # Penniless agents' resources should NOT be decremented by candidacy cost
        # Start 3.0 + fish 5.0 = 8.0 (if cost were deducted: 3.0 - 5.0 + 5.0 = 3.0)
        assert engine.get_agent("alice").resources == 8.0, \
            "Alice's resources should be 8.0 (3.0 start + 5.0 harvest, no candidacy deduction)"
        assert engine.get_agent("bob").resources == 8.0, \
            "Bob's resources should be 8.0 (3.0 start + 5.0 harvest, no candidacy deduction)"

    def test_vote_not_in_other_personal_logs(self):
        """A non-voter should NOT see another agent's vote in their personal log."""
        config = load_config({
            "simulation": {"num_rounds": 1, "turns_per_phase": 1},
            "agents": {"names": ["Alice", "Bob", "Charlie"], "starting_resources": 50.0},
            "resources": {"carrying_capacity": 100.0, "regeneration_factor": 1.5},
            "leader": {"fine_destination": "common_pool", "candidacy_cost": 2.0},
            "election": {"method": "plurality", "elections_every_round": True},
        })
        # 3 passes (free), 3 campaigns, 3 votes, 3 fish (harvest), 3 passes (post)
        responses = []
        for _ in range(3): responses.append(pass_response())  # free
        for _ in range(3): responses.append(campaign_response())  # campaigns
        for _ in range(3): responses.append(vote_response("alice"))  # votes
        for _ in range(3): responses.append(fish_response(5.0))  # harvest
        for _ in range(3): responses.append(pass_response())  # post

        stub = StubLLM(responses)
        engine = Engine(config, llm=stub, seed=42)
        engine.run()

        # Check Alice's personal log — should have a vote entry
        alice = engine.get_agent("alice")
        alice_votes = [e for e in alice.personal_log if e["type"] == "vote"]
        assert len(alice_votes) >= 1

        # Check Charlie's personal log — should have exactly 1 vote entry (his own)
        charlie = engine.get_agent("charlie")
        charlie_votes = [e for e in charlie.personal_log if e["type"] == "vote"]
        assert len(charlie_votes) == 1, \
            f"Charlie should have exactly 1 vote entry, got {len(charlie_votes)}"
        assert charlie_votes[0]["data"]["voted_for"] == "alice", \
            f"Charlie voted for alice, got {charlie_votes[0]['data']['voted_for']}"

        # Count total vote entries across ALL agents — must equal number of voters (3)
        total_vote_entries = 0
        for aid in engine.agents:
            agent = engine.get_agent(aid)
            total_vote_entries += len([e for e in agent.personal_log if e["type"] == "vote"])
        assert total_vote_entries == 3, \
            f"Expected exactly 3 vote entries total (1 per voter), got {total_vote_entries}"


class TestEngineTransfer:
    """Test transfer action execution within the engine."""

    @pytest.fixture
    def simple_config(self):
        return load_config({
            "simulation": {"num_rounds": 1, "turns_per_phase": 1},
            "agents": {"names": ["Alice", "Bob"], "starting_resources": 50.0},
            "resources": {"carrying_capacity": 100.0, "regeneration_factor": 1.5},
            "leader": {"fine_destination": "common_pool"},
            "election": {"method": "plurality", "elections_every_round": False},
        })

    def test_transfer_event_recorded(self, simple_config):
        """Transfer action appears in output events."""
        # Give enough responses for all phases and agents.
        # The first free interaction phase will get a transfer response.
        stub = make_stub_responses(
            transfer_response("bob", 10.0),  # Agent A transfers to Agent B
            *[pass_response() for _ in range(5)],  # Remaining free + harvest + post
        )
        engine = Engine(simple_config, llm=stub, seed=42)
        engine.run()

        # At least one event in the output should be a transfer
        output = engine.get_output()
        all_actions = []
        for rnd in output["rounds"]:
            for phase in rnd["phases"]:
                for event in phase["turns"]:
                    all_actions.append(event["action"])

        assert "transfer" in all_actions, f"Expected transfer in actions: {all_actions}"


class TestFishInFreeInteraction:
    """Fish action works during free interaction phase."""

    def test_fish_dispatch_during_free_interaction(self):
        """LLM returning action='fish' during free interaction should catch fish."""
        config = load_config({
            "simulation": {"num_rounds": 1, "turns_per_phase": 1},
            "agents": {"names": ["Alice", "Bob"], "starting_resources": 50.0},
            "resources": {"carrying_capacity": 100.0, "regeneration_factor": 1.5, "fish_per_harvest": 5.0},
            "leader": {"fine_destination": "common_pool"},
            "election": {"method": "plurality", "first_election_round": 2},
        })
        stub = make_stub_responses(
            {"action": "fish", "amount": 8.0, "reasoning": "Need fish"},
            *[pass_response() for _ in range(5)],  # remaining turns
        )
        engine = Engine(config, llm=stub, seed=42)
        engine.run()

        # At least one agent should have more than starting resources (50 + fish caught)
        alice = engine.get_agent("alice")
        bob = engine.get_agent("bob")
        assert alice.resources > 50.0 or bob.resources > 50.0, \
            f"Expected someone to have > 50 fish, got A={alice.resources}, B={bob.resources}"


class TestHarvestPhase:
    """Harvest phase behavior when LLM returns pass or zero amount."""

    def test_harvest_pass_with_verbose_does_not_crash(self):
        """LLM returning pass during harvest with verbose=True and active leader should not NameError."""
        config = load_config({
            "simulation": {"num_rounds": 1, "turns_per_phase": 1},
            "agents": {"names": ["Alice"], "starting_resources": 50.0},
            "resources": {"carrying_capacity": 100.0, "regeneration_factor": 1.5},
            "leader": {"fine_destination": "common_pool"},
            "election": {"method": "plurality", "first_election_round": 2},
        })
        # Response: free_interaction pass, then harvest pass
        stub = StubLLM([
            {"action": "pass", "reasoning": "."},
            {"action": "pass", "reasoning": "."},
        ])
        engine = Engine(config, llm=stub, seed=42, verbose=True)
        # Advance to round 1 and set up leader so verbose path evaluates harvest_amount
        engine.current_round = 1
        engine.turn_counter = 0
        alice = engine.get_agent("alice")
        engine.leader = alice
        engine.leader_limit = 6.0
        engine.leader_penalty_rate = 2.0
        engine._harvested_this_round = {}
        # Free-interaction setup — consume first response
        engine.current_phase = "free_interaction"
        engine.recorder.start_round(1)
        engine.recorder.start_phase("free_interaction")
        engine._handle_agent_turn(alice)
        # Run harvest — if harvest_amount is undefined after guard, this will NameError
        engine._run_harvesting()
        assert alice.resources == 50.0, "Alice should not have fished"
        assert engine.pool.amount == 100.0, "Pool should remain full"

    def test_harvest_skips_when_action_is_pass(self):
        """LLM returning action='pass' during harvest should skip fishing."""
        config = load_config({
            "simulation": {"num_rounds": 1, "turns_per_phase": 1},
            "agents": {"names": ["Alice"], "starting_resources": 50.0},
            "resources": {"carrying_capacity": 100.0, "regeneration_factor": 1.5},
            "leader": {"fine_destination": "common_pool"},
            "election": {"method": "plurality", "first_election_round": 2},
        })
        # free_interaction pass, harvest pass, post-harvest pass
        stub = StubLLM([
            {"action": "pass", "reasoning": "."},
            {"action": "pass", "reasoning": "."},
            {"action": "pass", "reasoning": "."},
        ])
        engine = Engine(config, llm=stub, seed=42)
        engine.run()
        alice = engine.get_agent("alice")
        assert alice.resources == 50.0, "Alice should not have fished"
        assert engine.pool.amount == 100.0, "Pool should remain full"


class TestTalkChannelRouting:
    """Talk actions route through the agent's current channel."""

    def test_talk_routes_via_agent_channel(self):
        """Talk action sends message to channel members only, not third parties."""
        from simulation.llm_interface import StubLLM
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
        # Charlie stays in public

        # Send a talk via handle_agent_turn
        engine.llm = StubLLM(responses=[
            {"action": "talk", "message": "secret meeting", "reasoning": "."},
        ])
        engine.recorder.start_round(1)
        engine.recorder.start_phase("free_interaction")
        engine.current_round = 1
        engine.turn_counter = 5
        engine.current_phase = "free_interaction"
        engine._handle_agent_turn(alice)

        # Charlie should NOT have the talk entry
        charlie_secrets = [
            e for e in charlie.personal_log
            if e["type"] == "talk" and e["data"].get("message") == "secret meeting"
        ]
        assert len(charlie_secrets) == 0, "Charlie heard a private message"

        # Alice should have the talk entry (she's the speaker)
        alice_heard = any(
            e["type"] == "talk" and e["data"].get("message") == "secret meeting"
            for e in alice.personal_log
        )
        assert alice_heard, "Alice should have her own talk entry"

        # Bob should have the talk entry (he's in the channel)
        bob_heard = any(
            e["type"] == "talk" and e["data"].get("message") == "secret meeting"
            for e in bob.personal_log
        )
        assert bob_heard, "Bob should be in the channel and hear the message"


class TestMemoryContext:
    """Memory context no longer includes round_summary injection."""

    def test_round_summary_not_in_prompt(self):
        """The round_summary section (--- YOUR MEMORIES ---) no longer appears in context."""
        config = load_config({
            "simulation": {"num_rounds": 1, "turns_per_phase": 1},
            "agents": {"names": ["Alice", "Bob"], "starting_resources": 50.0},
            "resources": {"carrying_capacity": 100.0, "regeneration_factor": 1.5},
            "leader": {"fine_destination": "common_pool"},
            "election": {"method": "plurality", "elections_every_round": True},
        })
        responses = [pass_response() for _ in range(2)] + [campaign_response() for _ in range(2)] + [vote_response("alice") for _ in range(2)] + [fish_response(5.0) for _ in range(2)] + [pass_response() for _ in range(2)]
        stub = StubLLM(responses)
        engine = Engine(config, llm=stub, seed=42)
        engine.run()
        # Check that context built from _build_memory_context does NOT contain round_summary
        alice = engine.get_agent("alice")
        context = engine._build_memory_context(alice)
        assert "YOUR MEMORIES" not in context, "round_summary should not appear in memory context"
        # Reflections should still appear
        assert "YOUR LOG" in context


class TestPoolRegeneration:
    """Test resource pool regeneration between rounds."""

    def test_pool_regenerates_between_rounds(self):
        """Pool regrows after each round."""
        config = load_config({
            "simulation": {"num_rounds": 2, "turns_per_phase": 1},
            "agents": {"names": ["Alice", "Bob"], "starting_resources": 50.0},
            "resources": {"carrying_capacity": 100.0, "regeneration_factor": 2.0},
            "leader": {"fine_destination": "common_pool"},
            "election": {"method": "plurality", "first_election_round": 2},
        })

        # Round 1: pool starts at 100
        # Free interaction: 2 passes
        # Harvest: Alice=5, Bob=5 → pool=90
        # Round 1 ends: regenerate 90*2=180→capped at 100
        # Round 2: pool=100 again

        r1_responses = [
            pass_response(), pass_response(),  # free
            fish_response(5.0), fish_response(5.0),  # harvest
            pass_response(), pass_response(),  # post
        ]
        r2_responses = [
            pass_response(), pass_response(),  # free
            campaign_response(), campaign_response(),  # campaigns
            vote_response("alice"), vote_response("alice"),  # votes
            fish_response(5.0), fish_response(5.0),  # harvest
            pass_response(), pass_response(),  # post
        ]

        stub = make_stub_responses(*(r1_responses + r2_responses))
        engine = Engine(config, llm=stub, seed=42)
        engine.run()

        # Round 1 metrics: pool_remaining should be 90
        r1_metrics = engine.get_output()["metrics"]["by_round"][0]
        assert r1_metrics["pool_remaining"] == 90.0

        # Round 2: pool regenerated to 100, then 10 fished → 90 remaining
        r2_metrics = engine.get_output()["metrics"]["by_round"][1]
        assert r2_metrics["pool_remaining"] == 90.0


class TestReflectionPhase:
    """Reflection phase creates memories with vote self-reflection."""

    def test_reflection_memories_created(self):
        """After a round, each agent has reflection memories.

        Uses a custom StubLLM subclass that returns reflection content
        (StubLLM.reflect() returns empty by default).
        """
        class ReflectingStub(StubLLM):
            def reflect(self, prompt: str) -> list[dict]:
                return [{
                    "content": "I fished 5 fish this round. I plan to fish more next round.",
                    "significance": "personal",
                    "emotional_impact": "neutral",
                }]

        config = load_config({
            "simulation": {"num_rounds": 1, "turns_per_phase": 1},
            "agents": {"names": ["Alice", "Bob"], "starting_resources": 50.0},
            "resources": {"carrying_capacity": 100.0, "regeneration_factor": 1.5},
            "leader": {"fine_destination": "common_pool"},
            "election": {"method": "plurality", "elections_every_round": True},
        })
        # free(2), campaign(2), vote(2), harvest(2), post(2) = 10
        responses = [pass_response() for _ in range(2)] + [campaign_response() for _ in range(2)] + [vote_response("alice") for _ in range(2)] + [fish_response(5.0) for _ in range(2)] + [pass_response() for _ in range(2)]
        stub = ReflectingStub(responses)
        engine = Engine(config, llm=stub, seed=42)
        engine.run()
        for agent in engine.agent_list:
            reflections = [m for m in agent.memories if m.type == "reflection"]
            assert len(reflections) >= 1, f"{agent.name} has no reflection memories"
            for r in reflections:
                assert r.content, f"{agent.name} has empty reflection content"

    def test_reflection_prompt_contains_vote(self):
        """Reflection prompt for an agent includes their own vote record.

        Uses RecordingLLM to capture the prompt sent to reflect().
        """
        from simulation.llm_interface import RecordingLLM

        class RecordingStub(StubLLM):
            def reflect(self, prompt: str) -> list[dict]:
                self._last_reflect_prompt = prompt
                return [{
                    "content": "test reflection",
                    "significance": "personal",
                    "emotional_impact": "neutral",
                }]

        config = load_config({
            "simulation": {"num_rounds": 1, "turns_per_phase": 1},
            "agents": {"names": ["Alice", "Bob"], "starting_resources": 50.0},
            "resources": {"carrying_capacity": 100.0, "regeneration_factor": 1.5},
            "leader": {"fine_destination": "common_pool"},
            "election": {"method": "plurality", "elections_every_round": True},
        })
        responses = [pass_response() for _ in range(2)] + [campaign_response() for _ in range(2)] + [vote_response("alice") for _ in range(2)] + [fish_response(5.0) for _ in range(2)] + [pass_response() for _ in range(2)]
        stub = RecordingStub(responses)
        engine = Engine(config, llm=stub, seed=42)
        engine.run()
        # The reflection prompt should mention the agent's vote
        assert stub._last_reflect_prompt is not None
        assert "voted for" in stub._last_reflect_prompt


class TestChannelDissolution:
    """Tests 41-42: Private channels dissolve between phases."""

    def test_channels_dissolve_after_free_interaction(self):
        """After free_interaction ends, private channels are cleared — checked per boundary."""
        config = load_config({
            "simulation": {"num_rounds": 1, "turns_per_phase": 1},
            "agents": {"names": ["Alice", "Bob"], "starting_resources": 50.0},
            "resources": {"carrying_capacity": 100.0, "regeneration_factor": 1.5},
            "leader": {"fine_destination": "common_pool"},
            "election": {"method": "plurality", "elections_every_round": False},
        })
        stub = StubLLM([
            {"action": "create_group", "targets": ["bob"], "reasoning": "."},
            {"action": "pass", "reasoning": "."},  # bob's turn
            # harvest (2 agents × 1 turn)
            {"action": "fish", "amount": 5.0, "reasoning": "."},
            {"action": "fish", "amount": 5.0, "reasoning": "."},
            # post-harvest free interaction (2 agents × 1 turn)
            {"action": "pass", "reasoning": "."},
            {"action": "pass", "reasoning": "."},
        ])
        engine = Engine(config, llm=stub, seed=42)
        # Manually drive each phase so we can assert after every boundary
        engine._reset_round_state()
        engine.current_round = 1
        engine.recorder.start_round(1)

        # ── Phase 1: Free interaction ──
        engine._run_free_interaction()
        engine._dissolve_private_channels()
        for aid in engine.agents:
            assert engine.channels.agent_channel(aid) == "public", \
                f"{aid} should be in public after free_interaction dissolution"

        # ── Phase 2: Harvesting ──
        engine._run_harvesting()
        engine._dissolve_private_channels()
        for aid in engine.agents:
            assert engine.channels.agent_channel(aid) == "public", \
                f"{aid} should be in public after harvesting dissolution"

        # ── Phase 3: Post-harvest free interaction ──
        engine._run_free_interaction()
        engine._dissolve_private_channels()
        for aid in engine.agents:
            assert engine.channels.agent_channel(aid) == "public", \
                f"{aid} should be in public after post-harvest dissolution"
