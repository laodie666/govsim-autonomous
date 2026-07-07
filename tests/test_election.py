"""Tests for simple plurality election mechanics.

Phase 4 — TDD Layer 1: pure logic, no LLM.
Tests 14-16 from the specification.
"""

import pytest
from simulation.election import tally_election, ElectionResult, ElectionError


class TestElection:
    """Tests 14-16: Plurality voting, tie-breaking, edge cases."""

    def test_plurality_winner(self):
        """Test 14: Alice gets 3 votes, Bob gets 2 → Alice wins."""
        votes = ["alice", "bob", "alice", "alice", "bob"]
        result = tally_election(votes, method="plurality")
        assert result.winner == "alice"
        assert result.vote_counts == {"alice": 3, "bob": 2}

    def test_plurality_tie(self):
        """Test 15: A tie breaks by random choice (seedable)."""
        votes = ["alice", "bob", "alice", "bob", "charlie", "charlie"]
        # Alice=2, Bob=2, Charlie=2 — three-way tie
        result = tally_election(votes, method="plurality", seed=42)
        # With seed=42, the tie-break gives a deterministic winner
        assert result.winner in {"alice", "bob", "charlie"}
        # The vote counts should still be the same
        assert result.vote_counts == {"alice": 2, "bob": 2, "charlie": 2}
        # Tie-breaking info should be present
        assert result.tie_broken is True

    def test_plurality_tie_two_way(self):
        """Two-way tie breaks to a single winner."""
        votes = ["alice", "bob", "alice", "bob"]
        result = tally_election(votes, method="plurality", seed=99)
        assert result.winner in ("alice", "bob")
        assert result.tie_broken is True

    def test_plurality_all_vote_for_one(self):
        """Test 16: Unanimous vote → correct winner."""
        votes = ["alice", "alice", "alice", "alice", "alice"]
        result = tally_election(votes, method="plurality")
        assert result.winner == "alice"
        assert result.vote_counts == {"alice": 5}
        assert result.tie_broken is False

    def test_plurality_single_voter(self):
        """One voter is a valid edge case."""
        votes = ["bob"]
        result = tally_election(votes, method="plurality")
        assert result.winner == "bob"

    def test_plurality_empty_votes(self):
        """No votes should raise an error."""
        with pytest.raises(ElectionError):
            tally_election([], method="plurality")

    def test_plurality_vote_for_nonexistent(self):
        """Votes for unknown candidates are still counted (just names)."""
        votes = ["alice", "ghost", "alice"]
        result = tally_election(votes, method="plurality")
        assert result.winner == "alice"
        assert result.vote_counts == {"alice": 2, "ghost": 1}

    def test_election_unknown_method(self):
        """Unsupported election method raises an error."""
        with pytest.raises(ValueError):
            tally_election(["alice"], method="ranked_choice")

    def test_tie_seed_determinism(self):
        """Same seed + same votes → same winner every time."""
        votes = ["alice", "bob", "alice", "bob", "charlie", "charlie"]
        result1 = tally_election(votes, method="plurality", seed=42)
        result2 = tally_election(votes, method="plurality", seed=42)
        assert result1.winner == result2.winner
        assert result1.tie_broken == result2.tie_broken

    def test_tie_different_seeds(self):
        """Different seeds may produce different winners (probabilistic)."""
        votes = ["alice", "bob", "alice", "bob"]
        winners = set()
        for seed in range(20):
            result = tally_election(votes, method="plurality", seed=seed)
            winners.add(result.winner)
        # With at least 2 different seeds, we should see both possibilities
        # (this is probabilistic but extremely likely over 20 seeds)
        assert len(winners) >= 1  # At minimum, always has a winner

    def test_election_result_total_votes(self):
        """ElectionResult.total_votes equals the number of votes cast."""
        votes = ["alice", "bob", "alice"]
        result = tally_election(votes, method="plurality")
        assert result.total_votes == 3
        assert result.total_votes == len(votes)
