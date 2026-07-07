"""Tests for action types, validation, and execution.

Phase 5 — TDD Layer 1: pure logic, no LLM.
Tests 17-21 from the specification.
"""

import pytest
from simulation.agent import Agent
from simulation.actions import (
    TransferAction,
    validate_action,
    execute_transfer,
)


class TestActionValidation:
    """Tests 19-20: Action validation rules."""

    def test_action_validation_valid_transfer(self):
        """Test 19: Valid transfer action passes validation."""
        agent = Agent(id="alice", name="Alice", resources=50.0)
        action = TransferAction(
            agent_id="alice",
            target_id="bob",
            amount=10.0,
            reasoning="Sharing some fish",
        )
        result = validate_action(action, agent)
        assert result.valid is True

    def test_action_validation_insufficient_funds(self):
        """Test 18: Agent with 5 fish tries to transfer 10 → blocked."""
        agent = Agent(id="alice", name="Alice", resources=5.0)
        action = TransferAction(
            agent_id="alice",
            target_id="bob",
            amount=10.0,
            reasoning="Oops",
        )
        result = validate_action(action, agent)
        assert result.valid is False
        assert "insufficient" in result.reason.lower()

    def test_action_validation_transfer_to_self(self):
        """Test 19: Transferring to yourself → invalid."""
        agent = Agent(id="alice", name="Alice", resources=50.0)
        action = TransferAction(
            agent_id="alice",
            target_id="alice",
            amount=10.0,
            reasoning="To myself",
        )
        result = validate_action(action, agent)
        assert result.valid is False
        assert "self" in result.reason.lower()

    def test_action_validation_negative_amount(self):
        """Transfer with negative amount is invalid."""
        agent = Agent(id="alice", name="Alice", resources=50.0)
        action = TransferAction(
            agent_id="alice",
            target_id="bob",
            amount=-5.0,
            reasoning="?",
        )
        result = validate_action(action, agent)
        assert result.valid is False

    def test_action_validation_zero_amount(self):
        """Transfer of zero is valid (no-op)."""
        agent = Agent(id="alice", name="Alice", resources=50.0)
        action = TransferAction(
            agent_id="alice",
            target_id="bob",
            amount=0.0,
            reasoning="No-op",
        )
        result = validate_action(action, agent)
        assert result.valid is True


class TestTransferExecution:
    """Test 17: Transfer action execution."""

    def test_transfer_between_agents(self):
        """Test 17: Agent A gives 10 fish to Agent B."""
        agent_a = Agent(id="alice", name="Alice", resources=50.0)
        agent_b = Agent(id="bob", name="Bob", resources=30.0)

        action = TransferAction(
            agent_id="alice",
            target_id="bob",
            amount=10.0,
            reasoning="Sharing",
        )

        execute_transfer(action, agent_a, agent_b)

        assert agent_a.resources == 40.0
        assert agent_b.resources == 40.0

    def test_transfer_full_amount(self):
        """Transferring all resources."""
        agent_a = Agent(id="alice", name="Alice", resources=20.0)
        agent_b = Agent(id="bob", name="Bob", resources=30.0)

        action = TransferAction(
            agent_id="alice",
            target_id="bob",
            amount=20.0,
            reasoning="All of it",
        )

        execute_transfer(action, agent_a, agent_b)
        assert agent_a.resources == 0.0
        assert agent_b.resources == 50.0

    def test_transfer_zero(self):
        """Transfer of zero does nothing."""
        agent_a = Agent(id="alice", name="Alice", resources=50.0)
        agent_b = Agent(id="bob", name="Bob", resources=30.0)

        action = TransferAction(
            agent_id="alice",
            target_id="bob",
            amount=0.0,
            reasoning="No-op",
        )

        execute_transfer(action, agent_a, agent_b)
        assert agent_a.resources == 50.0
        assert agent_b.resources == 30.0

    def test_transfer_overdraft_caps(self):
        """Transferring more than available caps at sender resources."""
        agent_a = Agent(id="alice", name="Alice", resources=10.0)
        agent_b = Agent(id="bob", name="Bob", resources=30.0)

        action = TransferAction(
            agent_id="alice",
            target_id="bob",
            amount=50.0,  # Only has 10
            reasoning="Too generous",
        )

        execute_transfer(action, agent_a, agent_b)
        assert agent_a.resources == 0.0
        assert agent_b.resources == 40.0

    def test_transfer_exact_balance(self):
        """Transferring exactly what you have clears you out."""
        agent_a = Agent(id="alice", name="Alice", resources=10.0)
        agent_b = Agent(id="bob", name="Bob", resources=30.0)

        action = TransferAction(
            agent_id="alice",
            target_id="bob",
            amount=10.0,
            reasoning="All in",
        )

        execute_transfer(action, agent_a, agent_b)
        assert agent_a.resources == 0.0
        assert agent_b.resources == 40.0


class TestActionDataModel:
    """Low-level dataclass coverage."""

    def test_validation_result_valid(self):
        """ValidationResult for a valid action."""
        from simulation.actions import ValidationResult
        r = ValidationResult(valid=True)
        assert r.valid is True
        assert r.reason == ""

    def test_validation_result_invalid(self):
        """ValidationResult with a reason."""
        from simulation.actions import ValidationResult
        r = ValidationResult(valid=False, reason="Insufficient funds")
        assert r.valid is False
        assert "Insufficient" in r.reason

    def test_action_transfer_with_reasoning(self):
        """TransferAction includes reasoning."""
        action = TransferAction(
            agent_id="alice",
            target_id="bob",
            amount=15.0,
            reasoning="Repaying a debt",
        )
        assert action.reasoning == "Repaying a debt"



