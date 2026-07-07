"""Tests for the common-pool resource dynamics.

Phase 2 — TDD Layer 1: pure logic, no LLM.
Tests 3-7 from the specification.
"""

import pytest
from simulation.resource_pool import ResourcePool


class TestResourcePool:
    """Tests 3-7: Pool initialization, fishing, regeneration, boundaries."""

    def test_pool_initialization(self):
        """Test 3: Pool starts at carrying_capacity."""
        pool = ResourcePool(carrying_capacity=100.0)
        assert pool.amount == 100.0
        assert pool.carrying_capacity == 100.0

    def test_pool_fish(self):
        """Test 4: Pool.fish(amount) reduces pool by that amount, returns amount."""
        pool = ResourcePool(carrying_capacity=100.0)
        taken = pool.fish(10.0)
        assert taken == 10.0
        assert pool.amount == 90.0

    def test_pool_fish_exact_boundary(self):
        """Test 5: Pool.fish(pool.amount) drains it to 0."""
        pool = ResourcePool(carrying_capacity=50.0)
        taken = pool.fish(50.0)
        assert taken == 50.0
        assert pool.amount == 0.0

    def test_pool_fish_overdraft(self):
        """Test 6: Fishing more than available returns only what's left,
        and pool floors at 0."""
        pool = ResourcePool(carrying_capacity=30.0)
        taken = pool.fish(100.0)
        assert taken == 30.0  # Only what was available
        assert pool.amount == 0.0

    def test_pool_regenerate(self):
        """Test 7: Pool.regenerate(factor, cap) regrows but not above cap."""
        pool = ResourcePool(carrying_capacity=100.0)
        pool.fish(50.0)  # Down to 50
        pool.regenerate(factor=1.5, cap=100.0)
        assert pool.amount == 75.0  # 50 * 1.5 = 75

    def test_pool_regenerate_caps_at_carrying_capacity(self):
        """Regeneration never exceeds carrying_capacity."""
        pool = ResourcePool(carrying_capacity=100.0)
        pool.fish(5.0)  # Down to 95
        pool.regenerate(factor=2.0, cap=100.0)
        assert pool.amount == 100.0  # 95 * 2 = 190, capped to 100

    def test_pool_regenerate_from_empty(self):
        """Regenerating from an empty pool still produces some fish."""
        pool = ResourcePool(carrying_capacity=100.0)
        pool.fish(100.0)  # Empty
        pool.regenerate(factor=1.2, cap=100.0)
        # Floor at 5% of capacity = 5, then 5 * 1.2 = 6
        assert pool.amount == 6.0

    def test_pool_fish_zero(self):
        """Fishing 0 amount returns 0 and doesn't change the pool."""
        pool = ResourcePool(carrying_capacity=100.0)
        taken = pool.fish(0.0)
        assert taken == 0.0
        assert pool.amount == 100.0

    def test_pool_fish_negative(self):
        """Fishing a negative amount should raise an error."""
        pool = ResourcePool(carrying_capacity=100.0)
        with pytest.raises(ValueError):
            pool.fish(-5.0)

    def test_pool_regenerate_negative_factor(self):
        """Negative regeneration factor should raise an error."""
        pool = ResourcePool(carrying_capacity=100.0)
        with pytest.raises(ValueError):
            pool.regenerate(factor=-1.0, cap=100.0)

    def test_pool_initial_amount(self):
        """Pool can start with a custom initial amount below capacity."""
        pool = ResourcePool(carrying_capacity=100.0, initial_amount=50.0)
        assert pool.amount == 50.0
        assert pool.carrying_capacity == 100.0

    def test_pool_regenerate_custom_cap(self):
        """Regenerate with a custom cap value."""
        pool = ResourcePool(carrying_capacity=100.0, initial_amount=40.0)
        pool.regenerate(factor=2.0, cap=60.0)
        assert pool.amount == 60.0  # 40*2=80, capped to 60

    def test_pool_str_representation(self):
        """String representation shows current/capacity."""
        pool = ResourcePool(carrying_capacity=100.0)
        s = str(pool)
        assert "Pool" in s
        assert "100.0" in s
        assert "fish" in s

    def test_pool_fish_float_precision(self):
        """Fishing with floating point amounts works precisely."""
        pool = ResourcePool(carrying_capacity=100.0)
        taken = pool.fish(0.3)
        assert taken == 0.3
        assert abs(pool.amount - 99.7) < 0.001
