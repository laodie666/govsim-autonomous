"""Tests for agent state creation and resource management.

Phase 1 — TDD Layer 1 (pure unit tests, no LLM).
"""

import pytest
from simulation.agent import Agent, Memory


class TestAgentCreation:
    """Tests 1-2: Agent state creation and resource updates."""

    def test_agent_creation(self):
        """Test 1: Agent has correct id, name, starting resources,
        and initializes with empty memories and relationships."""
        agent = Agent(id="alice", name="Alice", resources=50.0)

        assert agent.id == "alice"
        assert agent.name == "Alice"
        assert agent.resources == 50.0
        assert agent.is_leader is False
        assert agent.voted_for is None
        assert agent.violations == 0
        assert agent.penalties_paid == 0.0
        assert agent.memories == []
        assert agent.turn_order_index == 0

    def test_agent_resource_update(self):
        """Test 2: Adding and deducting resources works correctly,
        and resources never go below zero."""
        agent = Agent(id="bob", name="Bob", resources=50.0)

        # Add resources
        agent.add_resources(10.0)
        assert agent.resources == 60.0

        # Deduct resources
        agent.deduct_resources(5.0)
        assert agent.resources == 55.0

        # Deduct more than available — should floor at 0
        agent.deduct_resources(100.0)
        assert agent.resources == 0.0

    def test_agent_negative_starting_resources(self):
        """Edge case: starting with zero resources should be valid."""
        agent = Agent(id="charlie", name="Charlie", resources=0.0)
        assert agent.resources == 0.0

    def test_agent_str_representation(self):
        """Agent string representation is readable."""
        agent = Agent(id="eve", name="Eve", resources=50.0)
        s = str(agent)
        assert "Eve" in s
        assert "50.0" in s or "50" in s

    def test_agent_str_leader(self):
        """Leader agent shows [LEADER] in string representation."""
        agent = Agent(id="eve", name="Eve", resources=50.0)
        agent.is_leader = True
        s = str(agent)
        assert "[LEADER]" in s

    def test_add_resources_negative_raises(self):
        """Adding negative resources raises ValueError."""
        agent = Agent(id="alice", name="Alice", resources=50.0)
        with pytest.raises(ValueError):
            agent.add_resources(-10.0)

    def test_deduct_resources_negative_raises(self):
        """Deducting negative resources raises ValueError."""
        agent = Agent(id="alice", name="Alice", resources=50.0)
        with pytest.raises(ValueError):
            agent.deduct_resources(-10.0)

    def test_add_resources_zero(self):
        """Adding zero is a no-op."""
        agent = Agent(id="alice", name="Alice", resources=50.0)
        agent.add_resources(0.0)
        assert agent.resources == 50.0

    def test_deduct_resources_zero(self):
        """Deducting zero is a no-op."""
        agent = Agent(id="alice", name="Alice", resources=50.0)
        agent.deduct_resources(0.0)
        assert agent.resources == 50.0


class TestRelationshipsAndMemory:
    """Coverage for memory and social state."""

    def test_add_memory_all_fields(self):
        """add_memory stores all provided fields correctly."""
        agent = Agent(id="alice", name="Alice", resources=50.0)
        mem = agent.add_memory(
            turn=5,
            type="observation",
            content="Bob gave 10 fish to Charlie",
            emotional_impact="negative",
            related_agents=["bob", "charlie"],
            significance="collusion",
        )
        assert mem.turn == 5
        assert mem.type == "observation"
        assert mem.content == "Bob gave 10 fish to Charlie"
        assert mem.emotional_impact == "negative"
        assert mem.related_agents == ["bob", "charlie"]
        assert mem.significance == "collusion"
        assert len(agent.memories) == 1

    def test_add_memory_defaults(self):
        """add_memory with minimal arguments fills in defaults."""
        agent = Agent(id="alice", name="Alice", resources=50.0)
        mem = agent.add_memory(turn=1, type="action", content="Passed")
        assert mem.emotional_impact == "neutral"
        assert mem.related_agents == []
        assert mem.significance is None

    def test_memory_dataclass_defaults(self):
        """Memory dataclass has correct defaults."""
        mem = Memory(turn=1, type="action", content="Something happened")
        assert mem.emotional_impact == "neutral"
        assert mem.related_agents == []
        assert mem.significance is None

    def test_multiple_memories_ordered(self):
        """Multiple memories are stored in insertion order."""
        agent = Agent(id="alice", name="Alice", resources=50.0)
        agent.add_memory(turn=1, type="action", content="First")
        agent.add_memory(turn=2, type="action", content="Second")
        agent.add_memory(turn=3, type="action", content="Third")
        assert agent.memories[0].content == "First"
        assert agent.memories[1].content == "Second"
        assert agent.memories[2].content == "Third"


class TestPersonality:
    """Tests for optional personality on Agent."""

    def test_default_no_personality(self):
        """Agent defaults to no personality."""
        agent = Agent(id="alice", name="Alice")
        assert agent.personality is None

    def test_personality_set(self):
        """Personality can be set on creation."""
        agent = Agent(id="bob", name="Bob", personality="greedy")
        assert agent.personality == "greedy"

    def test_personality_optional_on_create(self):
        """Agent with full args still accepts personality."""
        agent = Agent(id="emma", name="Emma", resources=50.0, personality="cooperative")
        assert agent.personality == "cooperative"
