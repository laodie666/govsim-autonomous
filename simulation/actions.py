"""Action types, validation, and execution for GovSim Autonomous.

Defines what agents can do each turn and the rules for those actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from simulation.agent import Agent


@dataclass
class TransferAction:
    """Specialized action data for resource transfers."""

    agent_id: str
    target_id: str
    amount: float
    reasoning: str = ""


@dataclass
class ValidationResult:
    """Result of validating an action."""

    valid: bool
    reason: str = ""


def validate_action(action: TransferAction, agent: Agent) -> ValidationResult:
    """Validate whether a transfer action is legal.

    Args:
        action: The proposed transfer.
        agent: The agent attempting the transfer.

    Returns:
        ValidationResult with valid flag and reason if invalid.
    """
    if action.amount < 0:
        return ValidationResult(False, "Cannot transfer negative resources")

    if action.target_id == action.agent_id:
        return ValidationResult(False, "Cannot transfer resources to yourself")

    if action.amount > agent.resources:
        return ValidationResult(
            False,
            f"Insufficient resources: have {agent.resources:.1f}, "
            f"need {action.amount:.1f}",
        )

    return ValidationResult(True)


def execute_transfer(action: TransferAction, sender: Agent, receiver: Agent) -> None:
    """Execute a resource transfer between two agents.

    The resources are deducted from the sender and added to the receiver.
    This assumes validation has already been done.

    Args:
        action: The transfer to execute.
        sender: The agent giving resources.
        receiver: The agent receiving resources.
    """
    actual_amount = min(action.amount, sender.resources)
    actual_amount = max(0.0, actual_amount)

    sender.deduct_resources(actual_amount)
    receiver.add_resources(actual_amount)
