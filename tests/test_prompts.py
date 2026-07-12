"""Tests for prompt templates — they must produce valid strings with all variables resolved."""

from simulation.prompts import (
    build_decision_prompt,
    build_campaign_prompt,
    build_vote_prompt,
    build_harvest_prompt,
    build_reflection_prompt,
)


class TestDecisionPrompt:
    def test_basic(self):
        prompt = build_decision_prompt(
            agent_name="Alice",
            resources=50.0,
            round_num=1,
            phase="free_interaction",
            leader_name=None,
            leader_limit=None,
            leader_penalty=None,
            pool_status="100.0 fish remaining",
        )
        assert "Alice" in prompt
        assert "Round 1" in prompt
        assert "free_interaction" in prompt
        assert "none" in prompt  # limit=none
        assert "Your fish" in prompt
        assert "Lake" in prompt

    def test_with_leader(self):
        prompt = build_decision_prompt(
            agent_name="Bob",
            resources=55.0,
            round_num=2,
            phase="free_interaction",
            leader_name="Alice",
            leader_limit=6.0,
            leader_penalty=2.0,
            pool_status="85.0 fish remaining",
            harvest_this_round=5.0,
        )
        assert "Bob" in prompt
        assert "Leader: Alice" in prompt
        assert "6.1" in prompt or "6.0" in prompt
        assert "2.0" in prompt
        assert "85.0" in prompt


class TestCampaignPrompt:
    def test_basic(self):
        prompt = build_campaign_prompt(
            agent_name="Alice",
            resources=50.0,
            opponents=["Bob", "Charlie"],
            pool_status="100.0 fish remaining",
        )
        assert "Alice" in prompt
        assert "Bob" in prompt
        assert "Charlie" in prompt
        assert "harvest_limit" in prompt
        assert "penalty_rate" in prompt

    def test_campaign_includes_memory_context(self):
        """Campaign prompt includes memory context (reflections, personal log)."""
        prompt = build_campaign_prompt(
            agent_name="Alice",
            resources=50.0,
            opponents=["Bob"],
            pool_status="100.0 fish remaining",
            memory_context="\n\n--- YOUR LOG ---\nBob betrayed you last round.",
            personality="greedy and manipulative",
        )
        assert "YOUR LOG" in prompt
        assert "Bob betrayed you" in prompt
        assert "Personality:" in prompt
        assert "greedy" in prompt


class TestVotePrompt:
    def test_basic(self):
        candidates = [
            {"name": "Alice", "harvest_limit": 5.0, "penalty_rate": 2.0, "message": "Vote Alice"},
            {"name": "Bob", "harvest_limit": 8.0, "penalty_rate": 1.0, "message": "Vote Bob"},
        ]
        prompt = build_vote_prompt(
            agent_name="Charlie",
            candidates=candidates,
        )
        assert "Charlie" in prompt
        assert "Alice" in prompt
        assert "Bob" in prompt
        assert "5.0" in prompt
        assert "8.0" in prompt
        assert "vote_for" in prompt

    def test_vote_includes_memory_context(self):
        """Vote prompt includes memory context (reflections, personal log)."""
        candidates = [
            {"name": "Alice", "harvest_limit": 5.0, "penalty_rate": 2.0, "message": "Vote Alice"},
        ]
        prompt = build_vote_prompt(
            agent_name="Charlie",
            candidates=candidates,
            memory_context="\n\n--- YOUR LOG ---\nAlice promised to lower the limit.",
            resources=45.0,
        )
        assert "YOUR LOG" in prompt
        assert "Alice promised" in prompt
        assert "45.0" in prompt


class TestHarvestPrompt:
    def test_basic(self):
        prompt = build_harvest_prompt(
            agent_name="Alice",
            resources=50.0,
            round_num=2,
            leader_name="Bob",
            limit=6.0,
            penalty_rate=2.0,
            pool_status="85.0 fish remaining",
        )
        assert "Alice" in prompt
        assert "Round 2" in prompt
        assert "6.0" in prompt
        assert "harvest" in prompt
        assert "85.0" in prompt
        assert "How many fish" in prompt
        assert "amount" in prompt or '"amount"' in prompt
        assert "Reply JSON" in prompt or "JSON" in prompt

    def test_harvest_includes_memory_context(self):
        """Harvest prompt includes memory context."""
        prompt = build_harvest_prompt(
            agent_name="Alice",
            resources=50.0,
            round_num=2,
            leader_name="Bob",
            limit=6.0,
            penalty_rate=2.0,
            pool_status="85.0 fish remaining",
            memory_context="\n\n--- YOUR LOG ---\nYou caught 5 fish last round.",
        )
        assert "YOUR LOG" in prompt
        assert "caught 5 fish" in prompt

    def test_harvest_prompt_asks_for_fish_action(self):
        """Harvest prompt asks for JSON with action='fish' and amount."""
        prompt = build_harvest_prompt(
            agent_name="Alice",
            resources=50.0,
            round_num=1,
            leader_name="Bob",
            limit=10.0,
            penalty_rate=2.0,
            pool_status="Pool: 100.0 fish remaining",
        )
        assert "How many fish" in prompt
        assert '"amount"' in prompt or "amount" in prompt
        assert "Reply JSON" in prompt or "JSON" in prompt


class TestReflectionPrompt:
    """Reflection prompt includes vote information."""

    def test_reflection_includes_vote(self):
        """Reflection prompt should mention the agent's own vote."""
        vote = {"voted_for": "alice", "round": 1}
        prompt = build_reflection_prompt(
            agent_name="Alice",
            round_num=1,
            vote_record=vote,
        )
        assert "voted for alice" in prompt.lower()

    def test_reflection_no_vote_still_works(self):
        """Reflection prompt works even without a vote record."""
        prompt = build_reflection_prompt(
            agent_name="Bob",
            round_num=1,
        )
        assert "voted for alice" not in prompt.lower()
        assert "reflecting" in prompt.lower()

    def test_reflection_has_personality(self):
        """Reflection prompt includes personality when set."""
        prompt = build_reflection_prompt(
            agent_name="Alice",
            round_num=1,
            personality="cautious and careful",
        )
        assert "cautious" in prompt


class TestEdgeCases:
    def test_decision_prompt_with_memory(self):
        prompt = build_decision_prompt(
            agent_name="Alice",
            resources=50.0,
            round_num=2,
            phase="free_interaction",
            leader_name="Bob",
            leader_limit=5.0,
            leader_penalty=1.0,
            pool_status="80.0",
            memory_context="\n\n--- RECENT MEMORIES ---\nBob betrayed you last round.",
        )
        assert "Bob betrayed you" in prompt
        assert "RECENT MEMORIES" in prompt

    def test_decision_prompt_harvest_this_round(self):
        prompt = build_decision_prompt(
            agent_name="Alice",
            resources=50.0,
            round_num=2,
            phase="free_interaction",
            leader_name="Bob",
            leader_limit=5.0,
            leader_penalty=1.0,
            pool_status="80.0",
            harvest_this_round=3.5,
        )
        # harvest_this_round is not shown in the new compact prompt format
        # The state line is concise: "Your fish: 50.0 | Lake: 80.0"
        assert "Your fish" in prompt

    def test_vote_prompt_no_messages(self):
        candidates = [
            {"name": "Alice", "harvest_limit": 5.0, "penalty_rate": 2.0},
            {"name": "Bob", "harvest_limit": 3.0, "penalty_rate": 4.0},
        ]
        prompt = build_vote_prompt(agent_name="Charlie", candidates=candidates)
        assert "Alice" in prompt
        assert "Bob" in prompt
        assert "5.0" in prompt


class TestPersonalityInPrompt:
    """Tests that personality is injected when set, absent when not."""

    def test_decision_prompt_no_personality(self):
        """No personality section when personality=None."""
        prompt = build_decision_prompt(
            agent_name="Alice", resources=50.0, round_num=1,
            phase="free_interaction", leader_name=None, leader_limit=None,
            leader_penalty=None, pool_status="100.0",
        )
        assert "Personality:" not in prompt

    def test_decision_prompt_with_personality(self):
        """Personality section appears when set."""
        prompt = build_decision_prompt(
            agent_name="Alice", resources=50.0, round_num=1,
            phase="free_interaction", leader_name=None, leader_limit=None,
            leader_penalty=None, pool_status="100.0",
            personality="greedy and manipulative",
        )
        assert "Personality:" in prompt
        assert "greedy and manipulative" in prompt

    def test_harvest_prompt_no_personality(self):
        """No personality in harvest prompt when not set."""
        prompt = build_harvest_prompt(
            agent_name="Alice", resources=50.0, round_num=2,
            leader_name="Bob", limit=6.0, penalty_rate=2.0,
            pool_status="85.0",
        )
        assert "Personality:" not in prompt

    def test_harvest_prompt_with_personality(self):
        """Personality appears in harvest prompt when set."""
        prompt = build_harvest_prompt(
            agent_name="Alice", resources=50.0, round_num=2,
            leader_name="Bob", limit=6.0, penalty_rate=2.0,
            pool_status="85.0", personality="cautious",
        )
        assert "Personality:" in prompt
        assert "cautious" in prompt

    def test_vote_prompt_includes_voter_personality(self):
        """Voter's own personality appears in the vote prompt."""
        candidates = [{"name": "Ash", "harvest_limit": 40.0, "penalty_rate": 3.0,
                       "message": "more fish for all"}]
        prompt = build_vote_prompt(
            agent_name="Sage", candidates=candidates,
            memory_context="", resources=30.0, personality="long-term conservationist",
        )
        assert "conservationist" in prompt

    def test_vote_prompt_includes_candidate_personalities(self):
        """Each candidate's personality is shown so voters can judge trust."""
        candidates = [
            {"name": "Ash", "harvest_limit": 40.0, "penalty_rate": 3.0, "message": "",
             "personality": "selfish and greedy"},
            {"name": "Sage", "harvest_limit": 5.0, "penalty_rate": 2.0, "message": "",
             "personality": "long-term conservationist"},
        ]
        prompt = build_vote_prompt(
            agent_name="River", candidates=candidates, resources=30.0,
        )
        assert "selfish and greedy" in prompt
        assert "conservationist" in prompt

    def test_vote_prompt_omits_personality_when_absent(self):
        """Backward compat: no personality section when none provided."""
        candidates = [{"name": "Ash", "harvest_limit": 40.0, "penalty_rate": 3.0, "message": ""}]
        prompt = build_vote_prompt(agent_name="Sage", candidates=candidates, resources=30.0)
        assert "Ash" in prompt
        assert "vote_for" in prompt
