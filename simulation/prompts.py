"""Prompt templates for LLM agent decisions.

Each builder receives the simulation context and returns a user prompt.
Static world rules, action definitions, and JSON format live in the
system prompt (llm_client.py). Only dynamic state goes here.
"""

from __future__ import annotations

from typing import Any, Optional


def build_reflection_prompt(
    agent_name: str,
    round_num: int,
    harvested: float = 0.0,
    penalty_msg: str = "",
    leader_name: str | None = None,
    resources: float = 0.0,
    vote_record: dict[str, Any] | None = None,
    personality: str | None = None,
) -> str:
    """Build the prompt for the reflection phase."""
    personality_block = f"\nPersonality: {personality}\n" if personality else ""

    vote_block = ""
    if vote_record and vote_record.get("voted_for"):
        vote_block = (
            f"\nYou voted for {vote_record['voted_for']}."
        )

    return (
        f"You are {agent_name}, reflecting on Round {round_num}."
        f"{personality_block}"
        f"\nHarvested: {harvested:.0f} fish"
        f"{penalty_msg}"
        f"\nLeader: {leader_name or 'None'}"
        f"\nYour fish: {resources:.0f}"
        f"{vote_block}"
        f"\nThink about what happened, what you learned, and what you plan next."
        f"\nReturn JSON: {{\"memories\": [{{\"content\":\"...\", \"significance\":\"...\", \"emotional_impact\":\"...\"}}]}}"
    )


def build_decision_prompt(
    agent_name: str,
    resources: float,
    round_num: int,
    phase: str,
    leader_name: Optional[str],
    leader_limit: Optional[float],
    leader_penalty: Optional[float],
    pool_status: str,
    harvest_this_round: float = 0.0,
    memory_context: str = "",
    personality: Optional[str] = None,
    last_action: str = "",
    phase_context: str = "",
) -> str:
    """Build the prompt for free interaction decisions.

    Static rules (actions, format) are in the system prompt.
    This contains only the agent's identity, state, and memory.
    """
    limit_str = f"{leader_limit:.1f}" if leader_limit is not None else "none"
    penalty_str = f"{leader_penalty:.1f}x" if leader_penalty else "none"

    lines = [f"You are {agent_name}. Round {round_num}, {phase}."]

    if personality:
        lines.append(f"\nPersonality: {personality}")
        lines.append("")

    # State line
    state = f"Your fish: {resources:.1f} | Lake: {pool_status}"
    if leader_name:
        state += f" | Leader: {leader_name} (limit={limit_str}, penalty={penalty_str})"
    else:
        state += f" | Leader: none | Limit: {limit_str}"
    lines.append(state)

    # Phase context
    if phase_context:
        lines.append(phase_context)

    # Last action
    if last_action:
        lines.append(f"Your last action: {last_action}")

    # Memory context (group, log, reflections, pending invites)
    if memory_context:
        lines.append(f"\n{memory_context}")

    return "\n".join(lines)


def build_campaign_prompt(
    agent_name: str,
    resources: float,
    opponents: list[str],
    pool_status: str,
    memory_context: str = "",
    personality: str | None = None,
) -> str:
    """Build the prompt for a candidate's campaign."""
    personality_block = f"\nPersonality: {personality}\n" if personality else ""

    return (
        f"You are {agent_name}, running for leader."
        f"{personality_block}"
        f"\nYour fish: {resources:.1f} | Lake: {pool_status}"
        f"\nOpponents: {', '.join(opponents)}"
        f"\n{memory_context}"
        f"\nPropose harvest limit (1-20) and penalty rate (0-5)."
        f"\nReply JSON: {{\"harvest_limit\":N, \"penalty_rate\":N, \"message\":\"...\", \"reasoning\":\"...\"}}"
    )


def build_vote_prompt(
    agent_name: str,
    candidates: list[dict],
    memory_context: str = "",
    resources: float = 0.0,
) -> str:
    """Build the prompt for a voting decision.

    candidates: list of {name, harvest_limit, penalty_rate, message}
    """
    lines = [f"You are {agent_name}, voting for leader."]
    if resources > 0:
        lines.append(f"Your fish: {resources:.1f}")

    lines.append(f"\n--- CANDIDATES ---")
    for c in candidates:
        lines.append(f"[{c['name']}] limit={c['harvest_limit']:.1f}, penalty={c['penalty_rate']:.1f}x")
        if c.get("message"):
            lines.append(f'  Says: "{c["message"]}"')
        lines.append("")

    if memory_context:
        lines.append(memory_context)
        lines.append("")

    lines.append(
        "Reply JSON: {\"vote_for\":\"candidate_id\", \"reasoning\":\"...\"}"
    )
    return "\n".join(lines)


def build_harvest_prompt(
    agent_name: str,
    resources: float,
    round_num: int,
    leader_name: Optional[str],
    limit: Optional[float],
    penalty_rate: Optional[float],
    pool_status: str,
    personality: Optional[str] = None,
    memory_context: str = "",
) -> str:
    """Build the prompt for the harvest phase."""
    personality_block = f"\nPersonality: {personality}\n" if personality else ""

    leader_block = ""
    if leader_name:
        leader_block = (
            f"Leader: {leader_name} (limit={limit:.1f}, penalty={penalty_rate:.1f}x)"
        )

    prompt = (
        f"You are {agent_name}. Round {round_num}, harvest."
        f"{personality_block}"
        f"\nYour fish: {resources:.1f} | Lake: {pool_status}"
    )
    if leader_block:
        prompt += f"\n{leader_block}"
    if memory_context:
        prompt += f"\n{memory_context}"
    prompt += "\nHow many fish do you take?"
    prompt += "\nReply JSON: {\"action\":\"fish\", \"amount\":N, \"reasoning\":\"...\"}"
    return prompt
