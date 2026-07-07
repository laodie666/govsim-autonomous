"""Agent state model for GovSim Autonomous.

Represents a single agent in the simulation, tracking their resources,
memories, and leader/voting state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Memory:
    """A single memory entry in an agent's memory store."""

    turn: int
    type: str                      # "observation" | "action" | "reflection" | "deal"
    content: str                   # Natural language description
    emotional_impact: str = "neutral"  # "positive" | "negative" | "neutral"
    related_agents: list[str] = field(default_factory=list)
    significance: Optional[str] = None  # "collusion" | "betrayal" | "alliance" | ...


@dataclass
class Agent:
    """State for a single agent in the simulation."""

    id: str
    name: str
    resources: float = 0.0
    is_leader: bool = False
    voted_for: Optional[str] = None
    violations: int = 0
    penalties_paid: float = 0.0
    personality: Optional[str] = None

    # Social state
    memories: list[Memory] = field(default_factory=list)

    # Personal log — chronological record of everything this agent sees/hears/does
    personal_log: list[dict] = field(default_factory=list)

    # Engine-internal
    turn_order_index: int = 0

    def add_resources(self, amount: float) -> None:
        """Add fish (or other resources) to this agent's stash."""
        if amount < 0:
            raise ValueError(f"Cannot add negative resources: {amount}")
        self.resources += amount

    def deduct_resources(self, amount: float) -> None:
        """Deduct fish from this agent's stash, flooring at zero."""
        if amount < 0:
            raise ValueError(f"Cannot deduct negative resources: {amount}")
        self.resources = max(0.0, self.resources - amount)

    def add_memory(
        self,
        turn: int,
        type: str,
        content: str,
        emotional_impact: str = "neutral",
        related_agents: Optional[list[str]] = None,
        significance: Optional[str] = None,
    ) -> Memory:
        """Add a memory to this agent's store."""
        memory = Memory(
            turn=turn,
            type=type,
            content=content,
            emotional_impact=emotional_impact,
            related_agents=related_agents or [],
            significance=significance,
        )
        self.memories.append(memory)
        return memory

    def add_log_entry(
        self,
        round_num: int,
        turn: int | None,
        phase: str | None,
        type: str,
        data: dict,
    ) -> None:
        """Add an entry to this agent's personal log."""
        self.personal_log.append({
            "round": round_num,
            "turn": turn,
            "phase": phase,
            "type": type,
            "data": data,
        })

    def __str__(self) -> str:
        leader_tag = " [LEADER]" if self.is_leader else ""
        return f"{self.name}{leader_tag} ({self.resources:.1f} fish)"
