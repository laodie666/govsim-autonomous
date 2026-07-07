"""Tests for leader penalty calculation and fine distribution.

Phase 3 — TDD Layer 1: pure logic, no LLM.
Tests 8-13 from the specification.
"""

import pytest
from simulation.agent import Agent
from simulation.leader import calculate_penalty, distribute_fine
from simulation.resource_pool import ResourcePool


class TestPenaltyCalculation:
    """Tests 8-9: Penalty math is correct."""

    def test_penalty_calculation(self):
        """Test 8: penalty = max(0, harvest - limit) × rate.
        Agent fishes 8, limit is 5, rate is 2 → penalty = 6."""
        penalty = calculate_penalty(harvest_amount=8.0, limit=5.0, penalty_rate=2.0)
        assert penalty == 6.0

    def test_penalty_no_violation(self):
        """Test 9: max(0, 3 - 5) × 2 = 0 (no penalty for under-limit)."""
        penalty = calculate_penalty(harvest_amount=3.0, limit=5.0, penalty_rate=2.0)
        assert penalty == 0.0

    def test_penalty_exact_at_limit(self):
        """Harvesting exactly at the limit incurs no penalty."""
        penalty = calculate_penalty(harvest_amount=5.0, limit=5.0, penalty_rate=2.0)
        assert penalty == 0.0

    def test_penalty_zero_rate(self):
        """A penalty rate of 0 means no penalty regardless of excess."""
        penalty = calculate_penalty(harvest_amount=10.0, limit=5.0, penalty_rate=0.0)
        assert penalty == 0.0

    def test_penalty_negative_harvest(self):
        """Negative harvest amount should raise an error."""
        with pytest.raises(ValueError):
            calculate_penalty(harvest_amount=-1.0, limit=5.0, penalty_rate=2.0)

    def test_penalty_negative_limit(self):
        """Negative limit should raise an error."""
        with pytest.raises(ValueError):
            calculate_penalty(harvest_amount=5.0, limit=-1.0, penalty_rate=2.0)

    def test_penalty_negative_rate(self):
        """Negative penalty rate should raise an error."""
        with pytest.raises(ValueError):
            calculate_penalty(harvest_amount=5.0, limit=5.0, penalty_rate=-1.0)


class TestFineDistribution:
    """Tests 10-13: Where does the penalty fish go?"""

    def test_fine_to_leader_stash(self):
        """Test 10: Penalty deducted from violator, added to leader."""
        violator = Agent(id="alice", name="Alice", resources=50.0)
        leader = Agent(id="bob", name="Bob", resources=50.0)
        pool = ResourcePool(carrying_capacity=100.0)

        distribute_fine(
            penalty_amount=6.0,
            violator=violator,
            leader=leader,
            pool=pool,
            destination="leader_stash",
        )

        assert violator.resources == 44.0  # 50 - 6
        assert leader.resources == 56.0  # 50 + 6
        assert pool.amount == 100.0  # Unchanged

    def test_fine_to_common_pool(self):
        """Test 11: Penalty deducted from violator, added to pool."""
        violator = Agent(id="alice", name="Alice", resources=50.0)
        leader = Agent(id="bob", name="Bob", resources=50.0)
        pool = ResourcePool(carrying_capacity=100.0)
        pool.fish(20.0)  # Pool is now 80

        distribute_fine(
            penalty_amount=6.0,
            violator=violator,
            leader=leader,
            pool=pool,
            destination="common_pool",
        )

        assert violator.resources == 44.0  # 50 - 6
        assert leader.resources == 50.0  # Unchanged
        assert pool.amount == 86.0  # 80 + 6

    def test_fine_destroyed(self):
        """Test 12: Penalty deducted from violator, fish vanish."""
        violator = Agent(id="alice", name="Alice", resources=50.0)
        leader = Agent(id="bob", name="Bob", resources=50.0)
        pool = ResourcePool(carrying_capacity=100.0)

        distribute_fine(
            penalty_amount=6.0,
            violator=violator,
            leader=leader,
            pool=pool,
            destination="destroyed",
        )

        assert violator.resources == 44.0  # 50 - 6
        assert leader.resources == 50.0  # Unchanged
        assert pool.amount == 100.0  # Unchanged

    def test_fine_redistribute(self):
        """Test 13: Penalty deducted from violator, split equally among non-violators."""
        violator = Agent(id="alice", name="Alice", resources=50.0)
        leader = Agent(id="bob", name="Bob", resources=50.0)
        other = Agent(id="charlie", name="Charlie", resources=50.0)
        pool = ResourcePool(carrying_capacity=100.0)

        distribute_fine(
            penalty_amount=6.0,
            violator=violator,
            leader=leader,
            pool=pool,
            destination="redistribute",
            non_violators=[leader, other],
        )

        assert violator.resources == 44.0  # 50 - 6
        assert leader.resources == 53.0  # 50 + 3
        assert other.resources == 53.0  # 50 + 3
        assert pool.amount == 100.0  # Unchanged

    def test_fine_redistribute_no_non_violators(self):
        """Redistribute with only the violator should be a no-op (no one to give to)."""
        violator = Agent(id="alice", name="Alice", resources=50.0)
        leader = Agent(id="bob", name="Bob", resources=50.0)
        pool = ResourcePool(carrying_capacity=100.0)

        distribute_fine(
            penalty_amount=6.0,
            violator=violator,
            leader=leader,
            pool=pool,
            destination="redistribute",
            non_violators=[violator],  # Only the violator
        )

        assert violator.resources == 44.0  # Still deducted
        assert leader.resources == 50.0  # No one got it
        assert pool.amount == 100.0

    def test_fine_exceeds_violator_resources(self):
        """If penalty > violator's resources, violator goes to 0, rest is still distributed."""
        violator = Agent(id="alice", name="Alice", resources=5.0)
        leader = Agent(id="bob", name="Bob", resources=50.0)
        pool = ResourcePool(carrying_capacity=100.0)

        distribute_fine(
            penalty_amount=10.0,
            violator=violator,
            leader=leader,
            pool=pool,
            destination="leader_stash",
        )

        assert violator.resources == 0.0  # Floor at 0
        assert leader.resources == 55.0  # Got the 5 that existed
        assert pool.amount == 100.0

    def test_invalid_destination(self):
        """An unknown destination string should raise an error."""
        violator = Agent(id="alice", name="Alice", resources=50.0)
        leader = Agent(id="bob", name="Bob", resources=50.0)
        pool = ResourcePool(carrying_capacity=100.0)

        with pytest.raises(ValueError):
            distribute_fine(
                penalty_amount=6.0,
                violator=violator,
                leader=leader,
                pool=pool,
                destination="invalid_destination",
            )

    def test_fine_redistribute_default_non_violators(self):
        """Redistribute with non_violators=None (default) — no crash, no redistribution."""
        violator = Agent(id="alice", name="Alice", resources=50.0)
        leader = Agent(id="bob", name="Bob", resources=50.0)
        pool = ResourcePool(carrying_capacity=100.0)

        # redistribute with default None non_violators
        distribute_fine(
            penalty_amount=6.0,
            violator=violator,
            leader=leader,
            pool=pool,
            destination="redistribute",
            # non_violators defaults to None
        )

        # Penalty was deducted from violator
        assert violator.resources == 44.0
        # No one got it (no eligible non-violators)
        assert leader.resources == 50.0
        assert pool.amount == 100.0
