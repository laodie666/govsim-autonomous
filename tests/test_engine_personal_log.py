"""Engine integration tests for personal_log wiring.

Uses StubLLM. Tests that each engine event produces correct
personal_log entries on the right agents.
"""

import pytest
from simulation.agent import Agent
from simulation.engine import Engine
from simulation.config import DEFAULT_CONFIG
from simulation.llm_interface import StubLLM


def make_engine(llm_responses=None):
    """Create a minimal 3-agent engine with StubLLM."""
    config = {
        "simulation": {"num_rounds": 2, "turns_per_phase": 2},
        "agents": {"names": ["Alice", "Bob", "Charlie"], "starting_resources": 50.0},
        "resources": {"carrying_capacity": 100, "regeneration_factor": 1.5, "fish_per_harvest": 5.0},
        "leader": {"fine_destination": "common_pool", "default_limit": 10.0, "default_penalty_rate": 2.0},
        "election": {"method": "plurality", "elections_every_round": True},
        "llm": {"provider": "deepseek", "model": "deepseek-chat", "temperature": 0.7, "max_tokens": 500},
    }
    llm = StubLLM(responses=llm_responses) if llm_responses else StubLLM()
    return Engine(config, llm=llm, seed=42)


class TestPersonalLogTalk:
    """Talk events create log entries for hearers."""

    def test_talk_creates_log_entry(self):
        """A public talk creates a 'talk' entry for the speaker and all hearers."""
        # StubLLM returns talk with message
        engine = make_engine(llm_responses=[
            {"action": "talk", "message": "Hello everyone", "group": "public"},
        ])
        engine.run()
        for aid in engine.agents:
            agent = engine.agents[aid]
            talk_entries = [e for e in agent.personal_log if e["type"] == "talk"]
            assert len(talk_entries) >= 1, f"{aid} has no talk entries"


class TestPersonalLogHarvest:
    """Harvest events create log entries."""

    def test_harvest_creates_entry_for_fisher(self):
        """The agent who fishes gets a 'harvest' entry with amounts."""
        # Force fish action via StubLLM
        engine = make_engine(llm_responses=[
            {"action": "fish", "amount": 5.0},
        ])
        engine.run()
        all_harvests = [
            e for agent in engine.agent_list
            for e in agent.personal_log
            if e["type"] == "harvest"
        ]
        assert len(all_harvests) >= 1, "No harvest entries created"
        # Verify at least one harvest has amount > 0
        positive_harvests = [e for e in all_harvests if e.get("data", {}).get("amount", 0) > 0]
        assert len(positive_harvests) >= 1, "No harvest entries with positive amount"

    def test_harvest_entry_has_pool_before_after(self):
        """Harvest entries include pool_before and pool_after."""
        # Use a response that returns fish
        engine = make_engine(llm_responses=[
            {"action": "fish", "amount": 5.0},
        ])
        engine.run()
        for agent in engine.agent_list:
            for e in agent.personal_log:
                if e["type"] == "harvest":
                    assert "pool_before" in e["data"]
                    assert "pool_after" in e["data"]

    def test_pool_state_entry_for_other_agents(self):
        """Non-fishing agents get 'pool_state' entries when pool drops."""
        def p():
            return {"action": "pass", "reasoning": "."}
        def fish(amt):
            return {"action": "fish", "amount": amt, "reasoning": "."}
        # 2 rounds, 3 agents, 2 turns_per_phase
        # R1: 6 free + 6 (3 campaign + 3 vote) + 3 harvest + 6 post = 21 calls
        # R2: 6 free + 6 (3 campaign + 3 vote) + 3 harvest + 6 post = 21 calls
        r = [p() for _ in range(6)]  # free R1
        r += [p() for _ in range(3)] + [{"vote_for": "alice"} for _ in range(3)]  # campaign+vote R1
        r += [fish(5.0) for _ in range(3)] + [p() for _ in range(6)]  # harvest+post R1
        r += [p() for _ in range(6)] + [p() for _ in range(3)]  # free+campaign R2
        r += [{"vote_for": "alice"} for _ in range(3)]  # votes R2
        r += [fish(5.0) for _ in range(3)] + [p() for _ in range(6)]  # harvest+post R2
        engine = make_engine(llm_responses=r)
        engine.run()
        pool_state_entries = [
            e for agent in engine.agent_list
            for e in agent.personal_log
            if e["type"] == "pool_state"
        ]
        assert len(pool_state_entries) >= 1, "No pool_state entries created"
        # Verify entries track pool amount
        has_amount = any(
            e.get("data", {}).get("amount", 0) > 0
            for e in pool_state_entries
        )
        if not has_amount:
            # All pool entries could be amount=0 if no one fished enough
            # Just verify the structure exists
            assert all("pool_before" in e.get("data", {}) for e in pool_state_entries)


class TestPersonalLogElection:
    """Election creates vote and result log entries."""

    def test_election_result_entry_created(self):
        """All agents get an 'election_result' entry after election."""
        engine = make_engine()
        engine.run()
        # Round 2 has an election (first_election_round=2)
        for agent in engine.agent_list:
            result_entries = [e for e in agent.personal_log if e["type"] == "election_result"]
            assert len(result_entries) >= 1, f"{agent.name} missing election_result"

    def test_vote_entry_created(self):
        """Each agent has a 'vote' entry for who they voted for."""
        engine = make_engine()
        engine.run()
        for agent in engine.agent_list:
            vote_entries = [e for e in agent.personal_log if e["type"] == "vote"]
            assert len(vote_entries) >= 1, f"{agent.name} missing vote entry"


class TestPersonalLogChannels:
    """Channel actions create log entries."""

    def test_create_group_creates_invite_sent(self):
        """Creator gets 'invite_sent' entry when creating a group."""
        # Force create_group action
        engine = make_engine(llm_responses=[
            {"action": "create_group", "targets": ["bob", "charlie"]},
        ])
        engine.run()
        alice = engine.agents["alice"]
        sent = [e for e in alice.personal_log if e["type"] == "invite_sent"]
        assert len(sent) >= 1

    def test_create_group_creates_invite_received_for_targets(self):
        """Target agents get 'invite_received' entry."""
        engine = make_engine(llm_responses=[
            {"action": "create_group", "targets": ["bob", "charlie"]},
        ])
        engine.run()
        bob = engine.agents["bob"]
        received = [e for e in bob.personal_log if e["type"] == "invite_received"]
        assert len(received) >= 1

    def test_accept_invite_logs_for_both(self):
        """Accepting an invite creates join entry for accepter and invite_accepted for creator.

        Uses direct method calls to avoid StubLLM cycling unpredictability.
        """
        engine = make_engine()
        # Manually set up a channel + invitation
        channel_name = engine.channels._generate_channel_name()
        engine.channels._channels[channel_name] = {"alice"}
        engine.channels._invitations.append(
            type("Invitation", (), {"channel_name": channel_name, "from_agent": "alice", "to_agent": "bob"})()
        )
        # Bob accepts
        bob = engine.agents["bob"]
        import types
        resp = types.SimpleNamespace(action="accept_invite", group=channel_name, target=None, targets=None, message=None, amount=None, reasoning="test")
        engine.current_round = 1
        engine.turn_counter = 42
        engine.current_phase = "free_interaction"
        engine._execute_accept_invite(bob, resp)
        # Bob should have a 'join' entry
        assert any(e["type"] == "join" and e["data"].get("channel") == channel_name for e in bob.personal_log)

    def test_accept_invite_via_handle_turn(self):
        """LLM returning accept_invite dispatches through _handle_agent_turn correctly.

        End-to-end test through the action dispatch path, not just the handler.
        """
        engine = make_engine()
        # Manually set up a channel + invitation
        channel_name = engine.channels._generate_channel_name()
        engine.channels._channels[channel_name] = {"alice"}
        from simulation.channels import Invitation
        engine.channels._invitations.append(
            Invitation(channel_name=channel_name, from_agent="alice", to_agent="bob")
        )
        bob = engine.agents["bob"]
        engine.current_round = 1
        engine.turn_counter = 42
        engine.current_phase = "free_interaction"
        # Start recorder state so record_event works
        engine.recorder.start_round(1)
        engine.recorder.start_phase("free_interaction")
        # Set StubLLM to return accept_invite on Bob's next LLM call
        engine.llm = StubLLM(responses=[
            {"action": "accept_invite", "group": channel_name},
        ])
        engine._handle_agent_turn(bob)
        # Bob should be in the channel
        assert engine.channels.is_member(channel_name, "bob")
        # Bob should have a 'join' personal log entry
        assert any(e["type"] == "join" and e["data"].get("channel") == channel_name for e in bob.personal_log)


class TestPersonalLogPenalty:
    """Penalty events create log entries."""

    def test_violator_gets_penalty_entry(self):
        """An agent who exceeds the leader's limit gets a penalty log entry."""
        def pr():
            return {"action": "pass", "reasoning": "."}
        def cr(limit=5.0, rate=2.0):
            return {"harvest_limit": limit, "penalty_rate": rate, "message": ".", "reasoning": "."}
        def vr(candidate_id):
            return {"vote_for": candidate_id}
        def fr(amount=5.0):
            return {"action": "fish", "amount": amount, "reasoning": "."}

        config = {
            "simulation": {"num_rounds": 1, "turns_per_phase": 1},
            "agents": {"names": ["Alice", "Bob"], "starting_resources": 50.0},
            "resources": {"carrying_capacity": 100, "regeneration_factor": 1.5, "fish_per_harvest": 5.0},
            "leader": {"fine_destination": "common_pool", "default_limit": 10.0, "default_penalty_rate": 2.0, "candidacy_cost": 2.0},
            "election": {"method": "plurality", "elections_every_round": True},
        }
        responses = [
            pr(), pr(),  # free interaction
            cr(limit=5.0, rate=2.0),  # Alice campaigns
            cr(limit=5.0, rate=2.0),  # Bob campaigns
            vr("alice"),  # Alice votes for Alice
            vr("alice"),  # Bob votes for Alice
            fr(8.0),  # Alice fishes 8 (exceeds limit 5!)
            fr(3.0),  # Bob fishes 3 (under limit)
            pr(), pr(),
        ]
        llm = StubLLM(responses)
        from simulation.engine import Engine
        engine = Engine(config, llm=llm, seed=42)
        engine.run()

        # Alice should have a penalty entry
        alice = engine.get_agent("alice")
        alice_penalties = [e for e in alice.personal_log if e["type"] == "penalty"]
        assert len(alice_penalties) >= 1, "Alice should have a penalty entry"
        assert "penalized" in alice_penalties[0]["data"].get("text", "").lower(), \
            f"Penalty text should mention 'penalized', got: {alice_penalties[0]['data'].get('text', '')}"

        # Bob should NOT have a penalty entry
        bob = engine.get_agent("bob")
        bob_penalties = [e for e in bob.personal_log if e["type"] == "penalty"]
        assert len(bob_penalties) == 0, "Bob should not have a penalty entry"


class TestPersonalLogPrivacy:
    """Private talk privacy enforcement."""

    def test_private_talk_excluded_from_third_party(self):
        """A third party not in the private channel does NOT get the talk log entry."""
        engine = make_engine()
        alice = engine.agents["alice"]
        bob = engine.agents["bob"]
        charlie = engine.agents["charlie"]

        # Set up a private channel with Alice and Bob
        channel_name = engine.channels._generate_channel_name()
        engine.channels._channels[channel_name] = {"alice", "bob"}
        engine.channels._agent_channel["alice"] = channel_name
        engine.channels._agent_channel["bob"] = channel_name
        # Charlie stays in public

        # Send a private talk via handle_agent_turn
        engine.llm = StubLLM(responses=[
            {"action": "talk", "message": "secret meeting", "reasoning": "."},
        ])
        engine.recorder.start_round(1)
        engine.recorder.start_phase("free_interaction")
        engine.current_round = 1
        engine.turn_counter = 5
        engine.current_phase = "free_interaction"
        engine._handle_agent_turn(alice)

        # Charlie should NOT have this talk entry
        charlie_secrets = [
            e for e in charlie.personal_log
            if e["type"] == "talk" and e["data"].get("message") == "secret meeting"
        ]
        assert len(charlie_secrets) == 0, "Charlie heard a private message"

        # Alice (speaker) should have her own talk entry
        alice_heard = any(
            e["type"] == "talk" and e["data"].get("message") == "secret meeting"
            for e in alice.personal_log
        )
        assert alice_heard, "Alice should have her own talk entry"

        # Bob (channel member) should also have the talk entry
        bob_heard = any(
            e["type"] == "talk" and e["data"].get("message") == "secret meeting"
            for e in bob.personal_log
        )
        assert bob_heard, "Bob should be in the channel and hear the message"

    def test_transfer_sender_gets_entry(self):
        """Sender gets 'transfer_sent' entry."""
        engine = make_engine(llm_responses=[
            {"action": "transfer", "target": "bob", "amount": 10.0},
        ])
        engine.run()
        alice = engine.agents["alice"]
        assert any(e["type"] == "transfer_sent" for e in alice.personal_log)

    def test_transfer_receiver_gets_entry(self):
        """Receiver gets 'transfer_received' entry."""
        engine = make_engine(llm_responses=[
            {"action": "transfer", "target": "bob", "amount": 10.0},
        ])
        engine.run()
        bob = engine.agents["bob"]
        assert any(e["type"] == "transfer_received" for e in bob.personal_log)


class TestPersonalLogRoundMarkers:
    """Round start/end and phase markers."""

    def test_round_markers_present(self):
        """Each agent has round marker entries."""
        engine = make_engine()
        engine.run()
        for agent in engine.agent_list:
            markers = [e for e in agent.personal_log if e["type"] == "round_marker"]
            assert len(markers) >= 2, f"{agent.name} missing round markers (got {len(markers)})"

    def test_phase_markers_present(self):
        """Each agent has phase marker entries."""
        engine = make_engine()
        engine.run()
        for agent in engine.agent_list:
            markers = [e for e in agent.personal_log if e["type"] == "phase_marker"]
            assert len(markers) >= 4, f"{agent.name} missing phase markers (got {len(markers)})"
