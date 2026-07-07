"""Common-pool resource dynamics for GovSim Autonomous.

Tracks the shared fish population and handles fishing and regeneration.
"""

from __future__ import annotations


class ResourcePool:
    """A common-pool resource (e.g., a lake of fish).

    Attributes:
        amount: Current fish in the pool.
        carrying_capacity: Maximum fish the pool can hold.
    """

    def __init__(self, carrying_capacity: float, initial_amount: float | None = None):
        self.carrying_capacity = carrying_capacity
        self.amount = initial_amount if initial_amount is not None else carrying_capacity

    def fish(self, amount: float) -> float:
        """Remove fish from the pool.

        Args:
            amount: Desired amount to fish.

        Returns:
            Actual amount taken (may be less if pool is depleted).

        Raises:
            ValueError: If amount is negative.
        """
        if amount < 0:
            raise ValueError(f"Cannot fish negative amount: {amount}")
        taken = min(amount, self.amount)
        self.amount -= taken
        return taken

    def regenerate(self, factor: float, cap: float | None = None) -> None:
        """Regrow the fish population.

        Multiplicative growth from current amount, but always seeds at least
        5% of carrying capacity to prevent permanent extinction.

        Args:
            factor: Multiplier applied to (current amount, floored at 5% cap).
            cap: Maximum pool size after regeneration. If None, uses carrying_capacity.

        Raises:
            ValueError: If factor is negative.
        """
        if factor < 0:
            raise ValueError(f"Regeneration factor cannot be negative: {factor}")
        cap = cap if cap is not None else self.carrying_capacity
        # Floor at 5% of capacity so the pool never stays 0 permanently
        regen_from = max(self.amount, cap * 0.05)
        self.amount = min(cap, regen_from * factor)

    def __str__(self) -> str:
        return f"Pool: {self.amount:.1f}/{self.carrying_capacity:.1f} fish"
