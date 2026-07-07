"""Leader enforcement logic — penalty calculation and fine distribution.

Pure functions: no LLM involvement, fully deterministic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.agent import Agent
    from simulation.resource_pool import ResourcePool


VALID_DESTINATIONS = {"leader_stash", "common_pool", "destroyed", "redistribute"}


def calculate_penalty(
    harvest_amount: float, limit: float, penalty_rate: float
) -> float:
    """Calculate the penalty for exceeding a harvest limit.

    Formula: penalty = max(0, harvest - limit) × rate

    Args:
        harvest_amount: How many fish the agent took.
        limit: Per-agent harvest cap set by the leader.
        penalty_rate: Fish per excess fish the leader announced.

    Returns:
        The penalty amount in fish (always >= 0).

    Raises:
        ValueError: If any argument is negative.
    """
    if harvest_amount < 0:
        raise ValueError(f"Harvest amount cannot be negative: {harvest_amount}")
    if limit < 0:
        raise ValueError(f"Limit cannot be negative: {limit}")
    if penalty_rate < 0:
        raise ValueError(f"Penalty rate cannot be negative: {penalty_rate}")

    excess = max(0.0, harvest_amount - limit)
    return excess * penalty_rate


def distribute_fine(
    penalty_amount: float,
    violator: Agent,
    leader: Agent,
    pool: ResourcePool,
    destination: str,
    non_violators: list[Agent] | None = None,
) -> None:
    """Distribute a fine to its configured destination after a limit violation.

    The fine is always deducted from the violator first.
    What happens to those fish depends on destination:

    - "leader_stash": The leader receives the fish.
    - "common_pool": The fish go back to the shared resource pool.
    - "destroyed": The fish are removed from the system entirely.
    - "redistribute": The fish are split equally among non-violators.

    Args:
        penalty_amount: The penalty amount in fish to distribute.
        violator: The agent who violated the limit.
        leader: The current elected leader.
        pool: The shared resource pool.
        destination: Where the penalty fish should go.
        non_violators: List of agents who did not violate (for redistribute).

    Raises:
        ValueError: If destination is unknown.
    """
    if destination not in VALID_DESTINATIONS:
        raise ValueError(
            f"Unknown fine destination: '{destination}'. "
            f"Valid: {', '.join(sorted(VALID_DESTINATIONS))}"
        )

    # Deduct from violator (floor at 0)
    actual_penalty = min(penalty_amount, violator.resources)
    violator.deduct_resources(actual_penalty)

    if actual_penalty <= 0:
        return

    if destination == "leader_stash":
        leader.add_resources(actual_penalty)

    elif destination == "common_pool":
        pool.amount += actual_penalty

    elif destination == "destroyed":
        pass  # Fish vanish from the system

    elif destination == "redistribute":
        eligible = [a for a in (non_violators or []) if a.id != violator.id]
        if eligible:
            share = actual_penalty / len(eligible)
            for agent in eligible:
                agent.add_resources(share)
