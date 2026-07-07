#!/usr/bin/env python3
"""Debug utility: dump the full prompt an agent receives.

Usage:
    python debug_prompt.py                          # stub, 3 agents, Alice's first turn
    python debug_prompt.py --real                   # live DeepSeek
    python debug_prompt.py --agent bob              # a different agent
    python debug_prompt.py --turn 5                 # a specific turn number
    python debug_prompt.py --all                    # dump all agents' prompts
    python debug_prompt.py --after                  # run full sim, then dump final state
"""

import argparse
import os
import sys
from pathlib import Path

# Ensure simulation is importable
sys.path.insert(0, str(Path(__file__).parent))

from simulation.agent import Agent
from simulation.engine import Engine
from simulation.llm_interface import StubLLM, LLMResponse
from simulation.llm_client import DeepSeekLLM


class PromptCaptureLLM(StubLLM):
    """Wraps StubLLM but captures the prompt text before returning."""

    def __init__(self, capture_file=None, responses=None):
        super().__init__(responses=responses)
        self.last_prompt = ""
        self.all_prompts: list[dict] = []
        self.capture_file = capture_file

    def decide(self, prompt: str) -> LLMResponse:
        self.last_prompt = prompt
        self.all_prompts.append({"turn": None, "agent": None, "prompt": prompt})
        if self.capture_file:
            with open(self.capture_file, "a", encoding="utf-8") as f:
                f.write(f"\n{'='*60}\nPROMPT\n{'='*60}\n{prompt}\n{'='*60}\n")
        return super().decide(prompt)


def run_stub():
    config = {
        "simulation": {"num_rounds": 2, "turns_per_phase": 2},
        "agents": {"names": ["Alice", "Bob", "Charlie"], "starting_resources": 50.0},
        "resources": {"carrying_capacity": 100, "regeneration_factor": 1.5, "fish_per_harvest": 5.0},
        "leader": {"fine_destination": "common_pool", "default_limit": 10.0, "default_penalty_rate": 2.0},
        "election": {"method": "plurality", "first_election_round": 2},
        "llm": {"provider": "deepseek", "model": "deepseek-chat", "temperature": 0.7, "max_tokens": 500},
    }
    # Use responses that exercise different action types
    responses = [
        # Round 1 Free Interaction (3 turns × 3 agents = 9 prompts)
        {"action": "talk", "message": "Hello everyone", "group": "public", "reasoning": "Greeting"},
        {"action": "talk", "message": "Hi Alice", "group": "public", "reasoning": "Reply"},
        {"action": "create_group", "targets": ["alice"], "reasoning": "Form alliance"},
        {"action": "talk", "message": "Let's cooperate", "group": "public", "reasoning": "Proposal"},
        {"action": "accept_invite", "group": "channel_0", "reasoning": "Join"},
        {"action": "talk", "message": "Good deal", "group": "public", "reasoning": "Agree"},
        {"action": "talk", "message": "I agree too", "group": "public", "reasoning": "Confirm"},
        {"action": "talk", "message": "Ready for harvest", "group": "public", "reasoning": "Prepare"},
        {"action": "pass", "reasoning": "Wait"},
        # Round 1 Harvest (3 agents)
        {"action": "fish", "amount": 20.0, "reasoning": "Take some"},
        {"action": "fish", "amount": 30.0, "reasoning": "Take more"},
        {"action": "fish", "amount": 0.0, "reasoning": "Pool empty"},
        # Round 1 Post-Harvest (3 agents × 2 turns = 6)
        {"action": "talk", "message": "Who took everything?", "group": "public", "reasoning": "Accuse"},
        {"action": "talk", "message": "Not me", "group": "public", "reasoning": "Deny"},
        {"action": "pass", "reasoning": "Thinking"},
        {"action": "talk", "message": "Let's set rules", "group": "public", "reasoning": "Propose"},
        {"action": "talk", "message": "Agreed", "group": "public", "reasoning": "Agree"},
        {"action": "pass", "reasoning": "Done"},
        # Round 2 Free Interaction (3 × 2 = 6)
        {"action": "talk", "message": "New round new rules", "group": "public", "reasoning": "Fresh start"},
        {"action": "talk", "message": "I'll be honest", "group": "public", "reasoning": "Promise"},
        {"action": "create_group", "targets": ["bob", "charlie"], "reasoning": "Private chat"},
        {"action": "talk", "message": "I saw what happened", "group": "public", "reasoning": "Call out"},
        {"action": "accept_invite", "group": "channel_1", "reasoning": "Join"},
        {"action": "accept_invite", "group": "channel_1", "reasoning": "Join too"},
        # Round 2 Election (6 prompts: 3 campaign + 3 vote)
        {"action": "talk", "message": "Vote for me", "group": "public", "reasoning": "Campaign"},
        {"action": "talk", "message": "I'm better", "group": "public", "reasoning": "Campaign"},
        {"action": "talk", "message": "I'll be fair", "group": "public", "reasoning": "Campaign"},
        # Vote results come from Engine._run_election calling llm.vote()
        # That returns a vote dict, not an action — handled separately
        # Round 2 Harvest (3 agents)
        {"action": "fish", "amount": 10.0, "reasoning": "Within limit"},
        {"action": "fish", "amount": 5.0, "reasoning": "Conservative"},
        {"action": "fish", "amount": 0.0, "reasoning": "Save pool"},
        # Round 2 Post-Harvest (3 × 2 = 6)
        {"action": "talk", "message": "Good harvest", "group": "public", "reasoning": "Satisfied"},
        {"action": "talk", "message": "Leader worked out", "group": "public", "reasoning": "Approval"},
        {"action": "pass", "reasoning": "Wait"},
        {"action": "talk", "message": "Next round", "group": "public", "reasoning": "Plan"},
        {"action": "talk", "message": "I'm leaving", "group": "public", "reasoning": "Done"},
        {"action": "pass", "reasoning": "End"},
    ]
    capture = PromptCaptureLLM(responses=responses)
    engine = Engine(config, llm=capture, seed=42)
    engine.run()
    return engine, capture


def main():
    parser = argparse.ArgumentParser(description="Debug prompt content")
    parser.add_argument("--real", action="store_true", help="Run with DeepSeek (not stub)")
    parser.add_argument("--agent", default=None, help="Dump only this agent's prompts")
    parser.add_argument("--turn", type=int, default=None, help="Dump only this turn number")
    parser.add_argument("--all", action="store_true", help="Dump all prompts")
    parser.add_argument("--after", action="store_true", help="Dump personal_log after run (not prompts)")
    args = parser.parse_args()

    engine, capture = run_stub()

    if args.after:
        # Dump personal_log for all agents
        for agent in engine.agent_list:
            print(f"\n{'='*60}")
            print(f"  {agent.name}'s PERSONAL LOG")
            print(f"{'='*60}")
            for entry in agent.personal_log:
                _dump_entry(entry)
        return

    # Dump prompts
    for i, p in enumerate(capture.all_prompts):
        # Extract agent and turn if available
        prompt = p["prompt"]
        # Try to find agent name in the prompt
        agent_name = "?"
        for line in prompt.split("\n"):
            if line.startswith("You are ") and " in a resource-sharing" in line:
                agent_name = line[8:].split(" in a resource-sharing")[0]
                break

        turn_info = ""
        for line in prompt.split("\n"):
            if line.startswith("Round:") and "Phase:" in prompt:
                pass
            if "Turn:" in prompt:
                # Not in current prompt format, skip
                pass

        # Find round and phase
        round_num = "?"
        phase = "?"
        for line in prompt.split("\n"):
            if line.startswith("Round:"):
                round_num = line.split(":")[1].strip()
            if line.startswith("Phase:"):
                phase = line.split(":")[1].strip()

        label = f"[{i:2d}] {agent_name:8s} | R{round_num} {phase:20s}"

        if args.agent and args.agent.lower() not in agent_name.lower():
            continue

        print(f"\n{'='*60}")
        print(f"  PROMPT {label}")
        print(f"{'='*60}")
        print(prompt)
        print(f"{'='*60}\n")


def _dump_entry(entry: dict):
    """Print a single personal_log entry."""
    t = entry["type"]
    data = entry.get("data", {})
    r = entry.get("round", "?")
    turn = entry.get("turn", "-")

    if t == "talk":
        print(f"  R{r} T{turn} [{'public' if not data.get('channel') else data['channel']}] {data.get('speaker','?')}: \"{data.get('message','')}\"")
    elif t == "harvest":
        print(f"  R{r} T{turn} [HARVEST] You caught {data.get('amount',0):.1f} fish (pool: {data.get('pool_before','?')} -> {data.get('pool_after','?')})")
    elif t == "pool_state":
        print(f"  R{r} T{turn} [POOL] Someone caught fish (pool: {data.get('pool_before','?')} -> {data.get('pool_after','?')})")
    elif t == "vote":
        print(f"  R{r} T{turn} [VOTE] You voted for {data.get('voted_for','?')}")
    elif t == "election_result":
        print(f"  R{r} T{turn} [ELECTION] {data.get('winner','?')} wins (limit={data.get('limit','?')}, penalty={data.get('penalty_rate','?')}x)")
    elif t == "invite_sent":
        print(f"  R{r} T{turn} [SENT] You invited {data.get('to',[])} to {data.get('channel','?')} — waiting")
    elif t == "invite_received":
        print(f"  R{r} T{turn} [INVITE] {data.get('from','?')} invited you to {data.get('channel','?')}")
    elif t == "invite_accepted":
        print(f"  R{r} T{turn} [JOIN] {data.get('agent','?')} joined {data.get('channel','?')}")
    elif t == "invite_rejected":
        print(f"  R{r} T{turn} [REJECT] {data.get('agent','?')} declined {data.get('channel','?')}")
    elif t == "join":
        print(f"  R{r} T{turn} [JOIN] You joined {data.get('channel','?')} (members: {data.get('members',[])}")
    elif t == "leave":
        print(f"  R{r} T{turn} [LEAVE] You left {data.get('channel','?')}")
    elif t == "transfer_sent":
        print(f"  R{r} T{turn} [SEND] You sent {data.get('amount',0):.1f} fish to {data.get('to','?')}")
    elif t == "transfer_received":
        print(f"  R{r} T{turn} [RECV] {data.get('from','?')} sent you {data.get('amount',0):.1f} fish")
    elif t == "penalty":
        print(f"  R{r} T{turn} [PENALTY] {data.get('text','')}")
    elif t == "system":
        print(f"  R{r} T{turn} [SYS] {data.get('text','')}")
    elif t == "round_marker":
        print(f"  {'='*10} Round {data.get('round','?')} {'='*10}")
    elif t == "phase_marker":
        print(f"  --- {data.get('phase','?').upper()} ---")
    else:
        print(f"  R{r} T{turn} [{t.upper()}] {data}")


if __name__ == "__main__":
    main()
