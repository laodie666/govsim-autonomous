"""Core simulation engine -- orchestrates agents, phases, and rounds.

The engine is purely driven by LLMInterface calls. It does not know
about DeepSeek, OpenAI, or any specific provider.
"""

from __future__ import annotations

import concurrent.futures
import random
import time
from typing import Any, Optional

from simulation.agent import Agent
from simulation.resource_pool import ResourcePool
from simulation.actions import TransferAction, execute_transfer, validate_action
from simulation.leader import calculate_penalty, distribute_fine
from simulation.election import tally_election
from simulation.recorder import Recorder
from simulation.channels import ChannelManager
from simulation.llm_interface import LLMInterface, LLMResponse
from simulation.config import load_config
from simulation.prompts import (
    build_decision_prompt,
    build_nomination_prompt,
    build_campaign_prompt,
    build_vote_prompt,
    build_harvest_prompt,
    build_reflection_prompt,
)


class Engine:
    """The main simulation orchestrator.

    Usage:
        engine = Engine(config, llm=my_llm, seed=42)
        engine.run()
        output = engine.get_output()
    """

    def __init__(
        self,
        config: dict,
        llm: LLMInterface,
        seed: int | None = None,
        run_id: str | None = None,
        verbose: bool = False,
    ):
        self.config = config
        self.llm = llm
        self.rng = random.Random(seed)

        # Initialize state
        self.agents: dict[str, Agent] = {}
        self.agent_list: list[Agent] = []
        self.pool: ResourcePool | None = None
        self.leader: Agent | None = None
        self.leader_limit: float | None = None
        self.leader_penalty_rate: float | None = None

        # Recording
        import uuid
        self.recorder = Recorder(run_id=run_id or f"sim_{uuid.uuid4().hex[:12]}")
        self.recorder.set_config(config)
        self.verbose = verbose

        # Turn tracking
        self.current_round: int = 0
        self.current_phase: str | None = None
        self.turn_counter: int = 0
        self._last_action_desc: dict[str, str] = {}  # agent_id -> description of last action

        # Memory / conversation tracking
        self.conversation_log: list[dict] = []
        self._all_round_conversations: list[list[dict]] = []  # accumulated across rounds
        self._analysis_results: dict[int, str] = {}  # turn -> significance (set by post-hoc LLM)
        self.round_summaries: list[dict] = []
        self._penalties_this_round: dict[str, dict] = {}  # agent_id -> {amount, destination}
        self._pool_start: float = 0.0  # pool amount at round start
        self._election_data: dict | None = None  # most recent election result

        # Metrics tracking
        self._harvested_this_round: dict[str, float] = {}
        self._round_history: list[dict] = []  # per-round structured history
        self._violations_count: int = 0
        self._total_harvested: float = 0.0
        self._total_penalties_amount: float = 0.0

        # Collapse detection
        self.collapsed: bool = False
        self.collapsed_at_round: int | None = None
        self.survival_length: int = 0

        # Phase context sentence
        self._phase_context: str = ""
        self._current_turn_in_phase: int = 0

        # Initialize
        self.channels: ChannelManager | None = None  # initialized after agents in _init_state
        self._init_state()

    # ── action normalization ────────────────────────────────────────

    # Action aliases -- LLMs sometimes don't use exact enum values
    _ACTION_ALIASES: dict[str, str] = {
        "speak": "public_talk",
        "talk": "talk",
        "public_talk": "public_talk",
        "private_talk": "private_talk",
        "dm": "private_talk",
        "whisper": "private_talk",
        "create_group": "create_group",
        "create_channel": "create_group",
        "form_group": "create_group",
        "accept_invite": "accept_invite",
        "join": "accept_invite",
        "reject_invite": "reject_invite",
        "decline": "reject_invite",
        "leave_group": "leave_group",
        "leave": "leave_group",
        "transfer": "transfer",
        "send": "transfer",
        "give": "transfer",
        "fish": "fish",
        "harvest": "fish",
        "catch": "fish",
        "pass": "pass",
        "skip": "pass",
        "idle": "pass",
        "nominate": "nominate",
        "vote": "vote",
    }

    def _normalize_action(self, raw_action: str) -> str:
        """Normalize LLM action strings to canonical enum values."""
        action = raw_action.strip().lower() if raw_action else "pass"
        return self._ACTION_ALIASES.get(action, "pass")

    def _pool_status(self) -> str:
        """Return a human-readable pool status string."""
        return f"{self.pool.amount:.1f}/{self.pool.carrying_capacity:.1f} fish" if self.pool else "N/A"

    def _log_to_agents(self, agent_ids: list[str], type: str, data: dict) -> None:
        """Add a personal_log entry to specific agents.

        Uses current round, turn_counter, and phase from engine state.
        """
        for aid in agent_ids:
            agent = self.agents.get(aid)
            if agent:
                agent.add_log_entry(
                    round_num=self.current_round,
                    turn=self.turn_counter,
                    phase=self.current_phase,
                    type=type,
                    data=data,
                )

    def _log_to_all(self, type: str, data: dict) -> None:
        """Add a personal_log entry to every agent."""
        self._log_to_agents(list(self.agents.keys()), type, data)

    def _get_leader_name(self) -> str | None:
        """Return leader name or None if no leader (for prompt construction)."""
        return self.leader.name if self.leader else None

    def _dissolve_private_channels(self) -> None:
        """Dissolve all private channels, returning all agents to public.

        Called at the END of each phase that could create channels.
        """
        if self.channels:
            self.channels.dissolve_all()
            # Log for agents who were in private channels
            for agent in self.agent_list:
                if self.channels.agent_channel(agent.id) == "public":
                    pass  # all agents already back in public after dissolve
            # We can't distinguish who was in a private channel after dissolve,
            # but all agents are in public now, which is the normal state.

    def _capture_channel_snapshot(self) -> dict[str, list[str]]:
        """Capture current channel state for recorder output."""
        if not self.channels:
            return {}
        snapshot: dict[str, list[str]] = {}
        for aid, ch in self.channels._agent_channel.items():
            if ch not in snapshot:
                snapshot[ch] = []
            name = self.agents[aid].name
            snapshot[ch].append(name)
        return {ch: sorted(members) for ch, members in snapshot.items()}

    def _init_state(self) -> None:
        """Initialize agents and resource pool from config."""
        c = self.config
        agent_names = c["agents"]["names"]
        starting_resources = c["agents"]["starting_resources"]

        for i, name in enumerate(agent_names):
            agent_id = name.lower().replace(" ", "_")
            personalities = c["agents"].get("personalities", {})
            agent = Agent(
                id=agent_id,
                name=name,
                resources=starting_resources,
                turn_order_index=i,
                personality=personalities.get(name, None),
            )
            self.agents[agent_id] = agent
            self.agent_list.append(agent)

        self.pool = ResourcePool(
            carrying_capacity=c["resources"]["carrying_capacity"],
        )

        # Initialize channel system
        self.channels = ChannelManager([a.id for a in self.agent_list])

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Look up an agent by ID."""
        return self.agents.get(agent_id)

    def get_output(self) -> dict:
        """Get the complete simulation output."""
        return self.recorder.get_output()

    def save_output(self, path: str) -> None:
        """Save simulation output to a JSON file."""
        self.recorder.save(path)

    def run(self) -> None:
        """Run the full simulation from start to finish."""
        sim_start = time.time()
        num_rounds = self.config["simulation"]["num_rounds"]

        for round_num in range(1, num_rounds + 1):
            self.current_round = round_num
            self._reset_round_state()
            self.recorder.start_round(round_num)
            print(f"[sim] === Round {round_num}/{num_rounds} ===")

            # Personal log: round marker for all agents
            self._log_to_all("round_marker", {"round": round_num})

            # Snapshot pool at round start (after regeneration from previous round)
            self._pool_start = self.pool.amount
            print(f"[sim]   Pool: {self.pool.amount:.1f}/{self.pool.carrying_capacity}")

            # Phase 1: Free Interaction (pre-election)
            self._phase_context = "An election follows this phase. After that: harvest."
            print(f"[sim]   Phase: Free Interaction...")
            self._log_to_all("phase_marker", {"phase": "discussion"})
            self._run_free_interaction()
            self.recorder.set_channel_snapshot(self._capture_channel_snapshot())
            self._dissolve_private_channels()

            # Phase 2: Election (if applicable)
            first_election = self.config["election"].get("first_election_round")
            if first_election is not None:
                run_election = round_num >= first_election
            else:
                run_election = self.config["election"].get("elections_every_round", True)
            if run_election:
                print(f"[sim]   Phase: Election...")
                self._log_to_all("phase_marker", {"phase": "election"})
                self._run_election()
                self.recorder.set_channel_snapshot(self._capture_channel_snapshot())
                self._dissolve_private_channels()

            # Phase 3: Harvesting
            print(f"[sim]   Phase: Harvesting...")
            self._log_to_all("phase_marker", {"phase": "harvesting"})
            self._run_harvesting()
            self.recorder.set_channel_snapshot(self._capture_channel_snapshot())
            self._dissolve_private_channels()

            # Phase 4: Post-Harvest Interaction
            self._phase_context = "Discuss what happened and plan for next round."
            print(f"[sim]   Phase: Post-Harvest Interaction...")
            self._log_to_all("phase_marker", {"phase": "discussion"})
            self._run_free_interaction()
            self.recorder.set_channel_snapshot(self._capture_channel_snapshot())
            self._dissolve_private_channels()

            # Record end-of-round metrics
            self._record_round_metrics()

            # Check for pool collapse BEFORE regeneration
            if self.pool.amount < 0.01:
                self.collapsed = True
                self.collapsed_at_round = round_num
                self.survival_length = round_num
                print(f"[sim]   *** POOL COLLAPSED at round {round_num}")
                break

            # Regenerate resource pool
            self.pool.regenerate(
                factor=self.config["resources"]["regeneration_factor"],
            )

            self._build_round_summary(round_num)
            if self.verbose:
                print(f"[sim]     Summary generated, saving round history...")

            # Save this round's conversation history before resetting
            self._all_round_conversations.append(list(self.conversation_log))

            # Generate personal reflections for each agent
            if self.verbose:
                print(f"[sim]     Reflections...")
            self._call_reflections()
            if self.verbose:
                print(f"[sim]     Analysis...")

            # Post-hoc conversation analysis (separate LLM labels significance)
            self._analyze_conversation()

        # Set survival_length if not already set (normal completion)
        if not self.collapsed:
            self.survival_length = num_rounds

        # Populate recorder with end condition
        if self.collapsed:
            self.recorder.set_end_condition(
                end_condition="collapse",
                collapsed_at_round=self.collapsed_at_round,
                survival_length=self.survival_length,
            )
        else:
            self.recorder.set_end_condition(
                end_condition="time_limit",
                collapsed_at_round=None,
                survival_length=self.survival_length,
            )

        # Populate recorder with round summaries and agent memories
        self._set_recorder_metadata()

        # Final summary
        wall_clock = time.time() - sim_start
        end_reason = f"collapse at round {self.collapsed_at_round}" if self.collapsed else "time limit"
        print(f"[sim] === Simulation complete: {self.survival_length} round(s), ended: {end_reason} ({wall_clock:.1f}s wall) ===")
        print(f"[sim] Total harvested: {self._total_harvested:.1f} fish, "
              f"Total penalties: {self._total_penalties_amount:.1f} fish")
        llm_stats = self.llm.stats()
        if llm_stats.get("calls"):
            tokens = llm_stats.get("total_tokens", 0)
            time_s = llm_stats.get("total_time_ms", 0) / 1000
            cost = llm_stats.get("total_cost", 0.0)
            cost_str = f", ${cost:.4f}" if cost else ""
            print(f"[sim] LLM: {llm_stats['calls']} calls, {tokens} tokens{cost_str}, {time_s:.1f}s cumulative")

    def _reset_round_state(self) -> None:
        """Reset per-round tracking."""
        self.turn_counter = 0
        self.current_phase = None
        self._harvested_this_round = {}
        self._violations_count = 0
        self.leader_limit = None
        self.leader_penalty_rate = None
        self.conversation_log = []  # Clear per-round conversation
        # Note: full conversation history accumulates across rounds
        # in self._all_conversation (to be added below)
        self._penalties_this_round = {}
        self._election_data = None
        # _analysis_results is NOT cleared -- it accumulates across rounds
        # and is serialized once at the end in _set_recorder_metadata

    def _run_free_interaction(self) -> None:
        """Run a free interaction phase -- agents talk, transfer, or pass.

        Agents decide in parallel (Phase 1: read-only LLM calls),
        then execute sequentially (Phase 2: state mutations).
        """
        self.current_phase = "free_interaction"
        self.recorder.start_phase("free_interaction")

        turns = self.config["simulation"]["turns_per_phase"]
        order = self._shuffled_agents()
        if self.verbose:
            agent_names = [a.name for a in order]
            print(f"[sim]     Turn order: {', '.join(agent_names)}")

        for t in range(turns):
            self._current_turn_in_phase = t + 1
            if self.verbose:
                print(f"[sim]     Turn {t+1}/{turns}...")

            # Phase 1: All agents decide in parallel (read-only)
            decisions: dict[str, tuple] = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(order)) as ex:
                futures = {ex.submit(self._decide_for_agent, a): a for a in order}
                for future in concurrent.futures.as_completed(futures):
                    agent, ctx, resp, norm = future.result()
                    decisions[agent.id] = (ctx, resp, norm)

            # Phase 2: Execute sequentially, preserving deterministic order
            for agent in order:
                self.turn_counter += 1
                ctx, resp, norm = decisions[agent.id]
                self._execute_decision(agent, ctx, resp, norm)

    def _shuffled_agents(self) -> list[Agent]:
        """Return agents in a random order (seeded for reproducibility)."""
        agents = list(self.agent_list)
        self.rng.shuffle(agents)
        return agents

    def _handle_agent_turn(self, agent: Agent) -> None:
        """Process a single agent's decision (sequential, backward-compatible)."""
        agent, context, response, normalized = self._decide_for_agent(agent)
        self.turn_counter += 1
        self._execute_decision(agent, context, response, normalized)

    def _decide_for_agent(self, agent: Agent) -> tuple[Agent, str, LLMResponse, str]:
        """Phase 1: Build context + call LLM (read-only, safe to parallelize).
        Returns (agent, context, response, normalized_action).
        """
        context = self._build_context(agent)
        response = self.llm.decide(context)
        normalized = self._normalize_action(response.action)
        return agent, context, response, normalized

    def _execute_decision(self, agent: Agent, context: str, response: LLMResponse, normalized: str) -> None:
        """Phase 2: Execute action + record state (write, must be sequential)."""
        if self.verbose:
            if response.action not in ("pass",):
                msg = response.message or ""
                msg_snip = f" - \"{msg[:50]}\"" if msg else ""
                rsn = response.reasoning or ""
                rsn_snip = f" ({rsn[:40]})" if rsn and not msg else ""
                print(f"[sim]       {agent.name}: {response.action}{msg_snip}{rsn_snip}")

        # Record the event with resource state before
        resources_before = {
            agent.id: agent.resources,
            "pool": self.pool.amount if self.pool else 0,
        }

        # Execute the action
        if normalized in ("public_talk", "private_talk", "talk"):
            # Talk is handled inline via heard_by_set logic below
            pass
        elif normalized == "create_group":
            self._execute_create_group(agent, response)
        elif normalized == "accept_invite":
            self._execute_accept_invite(agent, response)
        elif normalized == "reject_invite":
            self._execute_reject_invite(agent, response)
        elif normalized == "leave_group":
            self._execute_leave_group(agent, response)
        elif normalized == "transfer":
            self._execute_transfer(agent, response)
        elif normalized == "fish":
            pool_before = self.pool.amount
            amount = response.amount or self.config["resources"].get("fish_per_harvest", 5.0)
            actual_taken = self.pool.fish(amount)
            agent.add_resources(actual_taken)
            agent.add_log_entry(
                round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
                type="harvest",
                data={"amount": actual_taken, "pool_before": pool_before, "pool_after": self.pool.amount},
            )
        # pass, unknown -- do nothing

        # Track last action for prompt context
        self._last_action_desc[agent.id] = self._describe_agent_action(agent, response, normalized)

        # Record the event with resource state after
        resources_after = {
            agent.id: agent.resources,
            "pool": self.pool.amount if self.pool else 0,
        }

        # Determine channel and heard_by for talk actions
        channel = None
        heard_by_set = None
        if response.message:
            if normalized == "talk":
                # Talk auto-routes to the agent's current group
                channel = self.channels.agent_channel(agent.id) if self.channels else "public"
                heard_by_set = self.channels.heard_by(channel) if self.channels else set(self.agents.keys())
            elif normalized == "private_talk":
                channel = "private"
                heard_by_set = {agent.id}
                if response.targets and len(response.targets) > 0:
                    heard_by_set.update(t for t in response.targets if t in self.agents)
                elif response.target and response.target in self.agents:
                    heard_by_set.add(response.target)
            else:
                # public_talk or other talk action with a message
                channel = "public"
                heard_by_set = set(self.agents.keys())

        self.recorder.record_event(
            turn=self.turn_counter,
            agent=agent.id,
            action=normalized,
            target=response.target,
            targets=response.targets,
            is_private=(channel is not None and channel != "public"),
            message=response.message,
            amount=response.amount,
            group=channel,  # talk group name (public or channel name), or None for non-talk
            heard_by=list(heard_by_set) if heard_by_set else None,
            reasoning=response.reasoning,
            resources_before=resources_before,
            resources_after=resources_after,
        )

        # Track in conversation log if there's a message
        if response.message:
            entry = {
                "turn": self.turn_counter,
                "agent": agent.id,
                "action": normalized,
                "message": response.message,
                "channel": channel,
                "is_private": (normalized == "private_talk"),
                "target": response.target,
                "targets": response.targets,
                "heard_by": heard_by_set,
            }
            self.conversation_log.append(entry)

            # Personal log: add talk entry to all hearers
            if normalized in ("talk", "public_talk", "private_talk"):
                speaker_name = agent.name
                for listener_id in heard_by_set:
                    listener = self.agents.get(listener_id)
                    if listener:
                        listener.add_log_entry(
                            round_num=self.current_round,
                            turn=self.turn_counter,
                            phase=self.current_phase,
                            type="talk",
                            data={
                                "channel": channel,
                                "speaker": speaker_name,
                                "message": response.message,
                                "is_private": (normalized == "private_talk"),
                            },
                        )

    def _execute_create_group(self, agent: Agent, response: LLMResponse) -> None:
        """Create a private channel and invite other agents."""
        members = [
            t.lower() for t in (response.targets or [])
            if t != agent.id and t.lower() in self.agents
        ]
        if response.target and response.target != agent.id and response.target.lower() in self.agents:
            if response.target.lower() not in members:
                members.append(response.target.lower())
        if not members:
            agent.add_log_entry(
                round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
                type="system",
                data={"text": f"Failed to create group: no valid targets in {response.targets}"},
            )
            return  # No valid targets

        # Check if this replaces a previous pending group
        old_pending = self.channels.get_pending_creator(agent.id)

        # Notify remaining public members that creator left public
        old_ch = self.channels.agent_channel(agent.id)
        if old_ch == "public":
            remaining = [a for a in self.agent_list if a.id != agent.id
                         and self.channels.agent_channel(a.id) == "public"]
            for other in remaining:
                other.add_log_entry(
                    round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
                    type="system",
                    data={"text": f"{agent.name} left public"},
                )

        channel_name = self.channels.create_private_channel(
            agent.id, members, message=response.message or ""
        )

        # Log if old pending was cancelled
        if old_pending:
            agent.add_log_entry(
                round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
                type="system",
                data={"text": f"You abandoned your old pending group ({old_pending}) to create {channel_name}"},
            )

        invite_msg = response.message or ""

        # Personal log: invite_sent for creator
        agent.add_log_entry(
            round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
            type="invite_sent",
            data={"to": members, "channel": channel_name, "message": invite_msg, "status": "pending"},
        )
        # Personal log: invite_received for each invitee
        for target_id in members:
            target = self.agents.get(target_id)
            if target:
                target.add_log_entry(
                    round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
                    type="invite_received",
                    data={"from": agent.name, "channel": channel_name, "message": invite_msg},
                )

    def _execute_accept_invite(self, agent: Agent, response: LLMResponse) -> None:
        """Accept an invitation to a private channel."""
        channel = response.group
        if not channel:
            # Try to find first pending invite
            if self.channels:
                pending = self.channels.get_pending_invitations(agent.id)
                if pending:
                    channel = pending[0].channel_name
                    agent.add_log_entry(
                        round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
                        type="system",
                        data={"text": f"You accepted the invite to {channel} (no channel specified, auto-selected)"},
                    )
                else:
                    agent.add_log_entry(
                        round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
                        type="system",
                        data={"text": "Failed to accept invite: no channel name specified and no pending invites"},
                    )
                    return
            else:
                return
        try:
            # Notify remaining public members that agent left
            if self.channels.agent_channel(agent.id) == "public":
                remaining = [a for a in self.agent_list if a.id != agent.id
                             and self.channels.agent_channel(a.id) == "public"]
                for other in remaining:
                    other.add_log_entry(
                        round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
                        type="system",
                        data={"text": f"{agent.name} left public"},
                    )

            # Check if accepting will cancel our own pending
            had_pending = self.channels.get_pending_creator(agent.id)

            self.channels.accept_invite(agent.id, channel)

            if had_pending:
                agent.add_log_entry(
                    round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
                    type="system",
                    data={"text": f"You abandoned your pending group creation because you joined {channel}"},
                )

            # Personal log: join entry for accepter
            agent.add_log_entry(
                round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
                type="join",
                data={"channel": channel, "from": "invite"},
            )
            # Personal log: notify channel members (find creator from invitations)
            for inv in self.channels._invitations:
                pass  # invitations accepted are removed, so we can't find them here
            # Alternative: log to all current channel members
            chan_members = self.channels.heard_by(channel)
            for mid in chan_members:
                if mid != agent.id:
                    m = self.agents.get(mid)
                    if m:
                        m.add_log_entry(
                            round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
                            type="invite_accepted",
                            data={"agent": agent.name, "channel": channel},
                        )
        except ValueError:
            pass

    def _execute_reject_invite(self, agent: Agent, response: LLMResponse) -> None:
        """Reject an invitation to a private channel."""
        channel = response.group
        if not channel:
            agent.add_log_entry(
                round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
                type="system",
                data={"text": "Failed to reject invite: no channel name specified"},
            )
            return
        try:
            # Find the creator before rejecting (rejection removes invitation)
            creator_name = None
            for inv in self.channels._invitations:
                if inv.to_agent == agent.id and inv.channel_name == channel:
                    creator = self.agents.get(inv.from_agent)
                    if creator:
                        creator_name = creator.name
                    break

            self.channels.reject_invite(agent.id, channel)
            agent.add_log_entry(
                round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
                type="invite_rejected",
                data={"channel": channel, "agent": agent.name},
            )
            # Personal log: notify the creator
            if creator_name:
                creator_agent = next((a for a in self.agent_list if a.name == creator_name), None)
                if creator_agent:
                    creator_agent.add_log_entry(
                        round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
                        type="invite_rejected",
                        data={"agent": agent.name, "channel": channel},
                    )
        except ValueError:
            pass

    def _execute_leave_group(self, agent: Agent, response: LLMResponse) -> None:
        """Leave a private channel."""
        channel = response.group
        if not channel or channel == "public":
            if not channel:
                agent.add_log_entry(
                    round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
                    type="system",
                    data={"text": "Failed to leave group: no channel name specified"},
                )
            elif channel == "public":
                agent.add_log_entry(
                    round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
                    type="system",
                    data={"text": "Cannot leave the public channel"},
                )
            return
        try:
            self.channels.leave(agent.id, channel)
            agent.add_log_entry(
                round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
                type="leave",
                data={"channel": channel},
            )
            # Notify public that agent returned
            public_members = [a for a in self.agent_list
                              if self.channels.agent_channel(a.id) == "public"]
            for other in public_members:
                if other.id != agent.id:
                    other.add_log_entry(
                        round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
                        type="system",
                        data={"text": f"{agent.name} returned to public"},
                    )
        except ValueError:
            pass

    def _execute_transfer(self, agent: Agent, response: LLMResponse) -> None:
        """Execute a resource transfer action."""
        target_id = response.target
        amount = response.amount or 0.0
        target_agent = self.get_agent(target_id.lower()) if target_id else None

        if target_agent and amount > 0:
            action = TransferAction(
                agent_id=agent.id,
                target_id=target_id,
                amount=amount,
                reasoning=response.reasoning,
            )
            # Validate before executing
            validation = validate_action(action, agent)
            if not validation.valid:
                # Transfer rejected -- record as pass with reason
                response.reasoning = f"Transfer rejected: {validation.reason}"
                response.action = "pass"
                return

            execute_transfer(action, agent, target_agent)
            # Personal log: transfer_sent for sender
            agent.add_log_entry(
                round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
                type="transfer_sent",
                data={"to": target_agent.name, "amount": amount},
            )
            # Personal log: transfer_received for receiver
            target_agent.add_log_entry(
                round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
                type="transfer_received",
                data={"from": agent.name, "amount": amount},
            )

    def _describe_agent_action(self, agent: Agent, response, normalized: str) -> str:
        """Describe the agent's last action in a short sentence for the prompt."""
        if normalized == "pass":
            return "passed"
        elif normalized in ("talk", "public_talk"):
            msg = response.message or ""
            return f'talk: "{msg[:60]}"' if msg else "talked"
        elif normalized == "private_talk":
            msg = response.message or ""
            return f'private_talk: "{msg[:60]}"' if msg else "sent a private message"
        elif normalized == "create_group":
            targets = response.targets or []
            if response.target and response.target not in targets:
                targets.append(response.target)
            return f"created group inviting {', '.join(targets)}" if targets else "created a group"
        elif normalized == "accept_invite":
            return f"joined {response.group}" if response.group else "accepted an invite"
        elif normalized == "reject_invite":
            return f"declined {response.group}" if response.group else "declined an invite"
        elif normalized == "leave_group":
            return f"left {response.group}" if response.group else "left a group"
        elif normalized == "transfer":
            target = response.target or "?"
            amt = response.amount or 0
            return f"sent {amt:.0f} fish to {target}"
        elif normalized == "fish":
            return f"fished {response.amount:.0f} fish" if response.amount else "fished"
        return normalized

    def _build_context(self, agent: Agent) -> str:
        """Build the full decision prompt using prompts.py templates."""
        leader_name = self._get_leader_name()
        harvest_this_round = sum(self._harvested_this_round.values())

        last_action = self._last_action_desc.get(agent.id, "")

        # Check for pending invites
        pending_invites_str = ""
        if self.channels:
            pending = self.channels.get_pending_invitations(agent.id)
            if pending:
                inv = pending[0]
                from_name = self.agents.get(inv.from_agent, Agent(id=inv.from_agent, name=inv.from_agent, resources=0)).name
                msg = f': "{inv.message}"' if inv.message else ""
                pending_invites_str = f"\n!! PENDING INVITE: {from_name} invited you to {inv.channel_name}{msg}\n"

        return build_decision_prompt(
            agent_name=agent.name,
            resources=agent.resources,
            round_num=self.current_round,
            phase=self.current_phase or "free_interaction",
            leader_name=leader_name,
            leader_limit=self.leader_limit,
            leader_penalty=self.leader_penalty_rate,
            pool_status=self._pool_status(),
            harvest_this_round=harvest_this_round,
            memory_context=self._build_round_history() + pending_invites_str + self._build_memory_context(agent),
            personality=agent.personality,
            last_action=last_action,
            phase_context=self._phase_context,
            turn_in_phase=self._current_turn_in_phase,
            turns_per_phase=self.config["simulation"]["turns_per_phase"],
            total_rounds=self.config["simulation"]["num_rounds"],
        )

    def _get_pending_sent_invites(self, agent_id: str) -> dict[str, dict]:
        """Find invites this agent sent that haven't been accepted yet.

        Returns dict of channel_name -> {"targets": [agent_ids], "message": str}
        """
        if not self.channels:
            return {}
        pending: dict[str, dict] = {}
        for invite in self.channels._invitations:
            if invite.from_agent == agent_id:
                if invite.channel_name not in pending:
                    pending[invite.channel_name] = {"targets": [], "message": invite.message}
                pending[invite.channel_name]["targets"].append(invite.to_agent)
        return pending

    def _build_round_history(self) -> str:
        """Build a structured round history section for the prompt."""
        if not self._round_history:
            return ""
        lines = ["=== ROUND HISTORY ==="]
        for rh in self._round_history:
            r = rh["round"]
            harvest_str = ", ".join(f"{name}: {amt:.1f}" for name, amt in rh["harvest"].items())
            lines.append(f"Round {r}:")
            if rh["winner"] and rh["winner"] != "None":
                lines.append(f"  Leader: {rh['winner']} (limit={rh['leader_limit']:.1f}, penalty={rh['leader_penalty']:.1f}x)")
                lines.append(f"  Votes: {rh['winner']} got {rh['winner_votes']} vote(s)")
            else:
                lines.append(f"  Leader: none (default limit=6.0, penalty=1.0x)")
            lines.append(f"  Catches: {harvest_str}")
            lines.append(f"  Total harvest: {rh['total_harvest']:.1f}")
            lines.append("")
        return "\n".join(lines)

    def _format_log_entry(self, entry: dict, agent: Agent) -> str:
        """Format a personal_log entry into a single readable line."""
        t = entry["type"]
        d = entry.get("data", {})

        if t == "talk":
            channel = d.get("channel", "public")
            speaker = d.get("speaker", "?")
            speaker_label = "You" if speaker == agent.name else speaker
            message = d.get("message", "")
            tag = f"[{channel}] "
            return f'{tag}{speaker_label}: "{message}"'

        elif t == "harvest":
            amount = d.get("amount", 0)
            pb = d.get("pool_before", "?")
            pa = d.get("pool_after", "?")
            return f"You caught {amount:.1f} fish (pool: {pb} -> {pa})"

        elif t == "pool_state":
            pb = d.get("pool_before", "?")
            pa = d.get("pool_after", "?")
            amt = d.get("amount", 0)
            return f"Pool: {pb} -> {pa} (someone took {amt:.1f} fish)"

        elif t == "vote":
            voted = d.get("voted_for", "?")
            voted_name = self.agents.get(voted, Agent(id=voted, name=voted, resources=0)).name
            return f"You voted for {voted_name}"

        elif t == "election_result":
            winner = d.get("winner", "?")
            lim = d.get("limit", "?")
            pen = d.get("penalty_rate", "?")
            return f"{winner} wins election (limit={lim}, penalty={pen}x)"

        elif t == "system":
            return d.get("text", "")

        elif t == "transfer_sent":
            to_name = d.get("to", "?")
            amt = d.get("amount", 0)
            return f"You sent {amt:.1f} fish to {to_name}"

        elif t == "transfer_received":
            from_name = d.get("from", "?")
            amt = d.get("amount", 0)
            return f"{from_name} sent you {amt:.1f} fish"

        elif t == "penalty":
            return d.get("text", "You were penalized")

        elif t == "invite_sent":
            to_list = d.get("to", [])
            to_names = [self.agents.get(i, Agent(id=i, name=i, resources=0)).name for i in to_list]
            channel_name = d.get("channel", "?")
            msg = d.get("message", "")
            msg_suffix = f': "{msg}"' if msg else ''
            return f"You invited {', '.join(to_names)} to {channel_name}{msg_suffix} — waiting"
        elif t == "invite_received":
            from_name = d.get("from", "?")
            channel_name = d.get("channel", "?")
            msg = d.get("message", "")
            msg_suffix = f': "{msg}"' if msg else ''
            return f"{from_name} invited you to {channel_name}{msg_suffix}"

        elif t == "invite_accepted":
            accepter = d.get("agent", "?")
            channel_name = d.get("channel", "?")
            return f"{accepter} joined {channel_name}"

        elif t == "invite_rejected":
            rejecter = d.get("agent", "?")
            channel_name = d.get("channel", "?")
            return f"{rejecter} declined to join {channel_name}"

        elif t == "join":
            channel_name = d.get("channel", "?")
            return f"You joined {channel_name}"

        elif t == "leave":
            channel_name = d.get("channel", "?")
            return f"You left {channel_name}"

        return ""

    def _build_memory_context(self, agent: Agent) -> str:
        """Build the memory context for an agent's decision prompt.

        Uses personal_log per agent (persistent chronological feed of
        everything the agent has seen/heard/done), channel status,
        pending invites, sent invites, reflections, and summaries.
        """
        parts: list[str] = []

        # 1. Current group + invites (single-group model)
        if self.channels:
            chan_lines = []
            current_ch = self.channels.agent_channel(agent.id)
            chan_members = self.channels.heard_by(current_ch)
            member_names = sorted(
                self.agents.get(m, Agent(id=m, name=m, resources=0)).name
                for m in chan_members
            )
            chan_lines.append(f"--- YOUR GROUP: {current_ch} ({', '.join(member_names)}) ---")


            # Pending invites TO this agent (with accept/reject templates)
            pending = self.channels.get_pending_invitations(agent.id)
            if pending:
                chan_lines.append("")
                chan_lines.append("--- PENDING INVITES (yours to act on) ---")
                for inv in pending:
                    from_name = self.agents.get(inv.from_agent, Agent(id=inv.from_agent, name=inv.from_agent, resources=0)).name
                    msg = f" \"{inv.message}\"" if inv.message else ""
                    chan_lines.append(f"  {from_name} invited you to {inv.channel_name}{msg}")
                    chan_lines.append(f"    -> Accept: {{\"action\": \"accept_invite\", \"group\": \"{inv.channel_name}\"}}")
                    chan_lines.append(f"    -> Reject: {{\"action\": \"reject_invite\", \"group\": \"{inv.channel_name}\"}}")

            # Pending invites SENT by this agent (waiting for response)
            sent_pending = self._get_pending_sent_invites(agent.id)
            if sent_pending:
                chan_lines.append("")
                chan_lines.append("--- YOUR PENDING INVITES (waiting) ---")
                for channel_name, info in sent_pending.items():
                    names = [self.agents.get(i, Agent(id=i, name=i, resources=0)).name for i in info["targets"]]
                    msg = f": \"{info['message']}\"" if info.get("message") else ""
                    chan_lines.append(f"  {channel_name}: waiting for {', '.join(names)}{msg}")

            # Show pending creation status (one-at-a-time constraint)
            pending_create = self.channels.get_pending_creator(agent.id)
            if pending_create:
                chan_lines.append("")
                remaining = [inv for inv in self.channels._invitations if inv.channel_name == pending_create]
                if remaining:
                    waiting_names = [self.agents.get(i.to_agent, Agent(id=i.to_agent, name=i.to_agent, resources=0)).name for i in remaining]
                    chan_lines.append(f"NOTE: You have a pending group creation ({pending_create}).")
                    chan_lines.append(f"      Waiting for: {', '.join(waiting_names)}")
                    chan_lines.append(f"      You must wait, abandon (create a new group), or join another group.")

            if chan_lines:
                parts.append("\n".join(chan_lines))

        # 2. Personal log -- chronological feed, last 1 round only
        log_entries = agent.personal_log
        if not log_entries:
            return "\n\n".join(parts) if parts else ""

        # Find the max round number present
        max_round = max(e.get("round", 0) or 0 for e in log_entries)
        min_round = max_round  # last 1 round only

        log_lines = ["--- YOUR LOG ---"]
        current_round_shown = None

        for entry in log_entries:
            e_round = entry.get("round", 0) or 0
            if e_round < min_round:
                continue

            # Round marker
            if e_round != current_round_shown and entry["type"] != "round_marker":
                current_round_shown = e_round
                log_lines.append(f"  === Round {e_round} ===")

            # Phase markers
            if entry["type"] == "phase_marker":
                phase_name = entry["data"].get("phase", "?").upper()
                log_lines.append(f"  --- {phase_name} ---")
                continue

            # Round markers
            if entry["type"] == "round_marker":
                r = entry["data"].get("round", "?")
                log_lines.append(f"  === Round {r} ===")
                current_round_shown = r
                continue

            # Format by type
            formatted = self._format_log_entry(entry, agent)
            if formatted:
                log_lines.append(f"  {formatted}")

        if len(log_lines) > 1:
            parts.append("\n".join(log_lines))

        # 3. Personal reflections (last 1 round only)
        reflections = [m for m in agent.memories if m.type == "reflection"]
        if reflections:
            lines = ["--- YOUR REFLECTIONS ---"]
            for m in reflections[-1:]:
                lines.append(f"  {m.content}")
            parts.append("\n".join(lines))

        return "\n\n".join(parts) if parts else ""
    def _run_election(self) -> None:
        """Run the election phase -- nomination, campaign + vote in parallel."""
        self.current_phase = "election"
        self.recorder.start_phase("election")

        # Phase 0: Nomination — ask each eligible agent if they want to run
        candidacy_cost = self.config["leader"].get("candidacy_cost", 5.0)
        candidates = []
        for agent in self.agent_list:
            if agent.resources < candidacy_cost:
                if self.verbose:
                    print(f"[sim]       {agent.name}: cannot afford candidacy cost ({candidacy_cost:.0f} fish)")
                agent.add_log_entry(round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
                    type="system",
                    data={"text": f"Cannot afford candidacy cost of {candidacy_cost:.0f} fish (have {agent.resources:.0f})"})
                continue

            # Ask agent if they want to run
            ctx = self._build_nomination_context(agent, candidacy_cost)
            wants_to_run = self.llm.nominate(ctx)
            self.turn_counter += 1

            if wants_to_run:
                agent.deduct_resources(candidacy_cost)
                candidates.append(agent)
                if self.verbose:
                    print(f"[sim]       {agent.name}: running for leader")
                agent.add_log_entry(round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
                    type="system",
                    data={"text": f"Declared candidacy for leader (paid {candidacy_cost:.0f} fish)"})
            else:
                if self.verbose:
                    print(f"[sim]       {agent.name}: declined to run")
                agent.add_log_entry(round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
                    type="system",
                    data={"text": "Declined to run for leader"})

        # Handle no-candidate fallback
        if not candidates:
            if self.verbose:
                print(f"[sim]       No candidates! Using default policy.")
            self.leader = None
            self.leader_limit = self.config["leader"]["default_limit"]
            self.leader_penalty_rate = self.config["leader"]["default_penalty_rate"]
            for agent in self.agent_list:
                agent.add_log_entry(round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
                    type="election_result",
                    data={"winner": "None (default policy)", "limit": self.leader_limit, "penalty_rate": self.leader_penalty_rate})
            self._election_data = {"winner": None, "votes": {}, "voter_map": {}}
            return

        if self.verbose:
            print(f"[sim]     Candidates: {[c.name for c in candidates]}")

        # === PHASE 1: Campaign in parallel ===
        candidate_platforms = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(candidates)) as ex:
            def _campaign(c):
                ctx = self._build_election_context(c, candidates)
                return c.id, self.llm.campaign(ctx)
            futures = {ex.submit(_campaign, c): c for c in candidates}
            for f in concurrent.futures.as_completed(futures):
                cid, platform = f.result()
                candidate_platforms[cid] = platform

        # Record campaign results sequentially
        for candidate in candidates:
            platform = candidate_platforms[candidate.id]
            self.recorder.record_event(turn=self.turn_counter + 1, agent=candidate.id,
                action="nominate", message=platform.message, reasoning=platform.reasoning,
                resources_before={candidate.id: candidate.resources},
                resources_after={candidate.id: candidate.resources})
            self.turn_counter += 1

        # === PHASE 2: Vote in parallel ===
        candidate_ids = [c.id for c in candidates]
        vote_results = []

        def _vote(voter):
            ctx = self._build_vote_context(voter, candidates, candidate_platforms)
            choice = self.llm.vote(ctx)
            if choice not in candidate_ids:
                choice = self.rng.choice(candidate_ids)
            return voter.id, choice

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.agent_list)) as ex:
            futures = {ex.submit(_vote, v): v for v in self.agent_list}
            for f in concurrent.futures.as_completed(futures):
                vid, choice = f.result()
                vote_results.append((vid, choice))

        # Record votes sequentially
        voter_map = {}
        for vid, choice in vote_results:
            voter_map[vid] = choice
            self.recorder.record_vote(vid, choice)
            voter = self.agents[vid]
            voter.add_log_entry(round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
                type="vote", data={"voted_for": choice})
            self.turn_counter += 1

        # === PHASE 3: Tally and declare winner ===
        vote_list = [voter_map[agent.id] for agent in self.agent_list]
        result = tally_election(vote_list, seed=self.rng.randint(0, 2**31))

        winner_id = result.winner
        winner_agent = self.agents[winner_id]
        winner_platform = candidate_platforms.get(winner_id)

        if self.leader:
            self.leader.is_leader = False
        self.leader = winner_agent
        self.leader.is_leader = True

        if winner_platform:
            self.leader_limit = winner_platform.harvest_limit
            self.leader_penalty_rate = winner_platform.penalty_rate

        self.recorder.record_election_result(winner=winner_id, votes=result.vote_counts,
            voter_map=voter_map,
            acceptance_message=winner_platform.message if winner_platform else None)
        self._election_data = {"winner": winner_id, "votes": result.vote_counts, "voter_map": voter_map}

        limit_str = self.leader_limit or "?"
        penalty_str = self.leader_penalty_rate or "?"
        for agent in self.agent_list:
            agent.add_log_entry(round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
                type="election_result",
                data={"winner": winner_agent.name, "limit": limit_str, "penalty_rate": penalty_str})

    def _build_election_context(self, candidate: Agent, candidates: list[Agent]) -> str:
        """Build campaign prompt using prompts.py."""
        opponents = [c.name for c in candidates if c.id != candidate.id]

        return build_campaign_prompt(
            agent_name=candidate.name,
            resources=candidate.resources,
            opponents=opponents,
            pool_status=self._pool_status(),
            memory_context=self._build_memory_context(candidate),
            personality=candidate.personality,
        )

    def _build_vote_context(
        self, voter: Agent, candidates: list[Agent], platforms: dict[str, Any]
    ) -> str:
        """Build vote prompt using prompts.py."""
        candidate_dicts = []
        for c in candidates:
            p = platforms.get(c.id)
            candidate_dicts.append({
                "name": c.name,
                "harvest_limit": p.harvest_limit if p else 0,
                "penalty_rate": p.penalty_rate if p else 0,
                "message": p.message if p else "",
            })

        return build_vote_prompt(
            agent_name=voter.name,
            candidates=candidate_dicts,
            memory_context=self._build_memory_context(voter),
            resources=voter.resources,
        )

    def _build_nomination_context(self, agent: Agent, candidacy_cost: float) -> str:
        """Build nomination prompt using prompts.py."""
        return build_nomination_prompt(
            agent_name=agent.name,
            resources=agent.resources,
            candidacy_cost=candidacy_cost,
            pool_status=self._pool_status(),
            memory_context=self._build_memory_context(agent),
            personality=agent.personality,
        )

    def _run_harvesting(self) -> None:
        """Run the harvesting phase -- agents fish.

        Decide in parallel (same pre-harvest pool), execute sequentially.
        """
        self.current_phase = "harvesting"
        self.recorder.start_phase("harvesting")

        self._current_turn_in_phase = 1
        order = self._shuffled_agents()
        if self.verbose:
            print(f"[sim]     Turn order: {[a.name for a in order]}")

        # Phase 1: All agents decide in parallel (same pool state)
        decisions = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(order)) as ex:
            def _harvest_decide(a):
                ctx = self._build_harvest_context(a)
                resp = self.llm.decide(ctx)
                return a.id, ctx, resp
            futures = {ex.submit(_harvest_decide, a): a for a in order}
            for f in concurrent.futures.as_completed(futures):
                aid, ctx, resp = f.result()
                decisions[aid] = (ctx, resp)

        # Phase 2: Execute sequentially (pool depletes)
        for agent in order:
            self.turn_counter += 1
            ctx, response = decisions[agent.id]

            resources_before = {
                agent.id: agent.resources,
                "pool": self.pool.amount if self.pool else 0,
            }

            harvest_amount = 0.0
            if response.action == "pass" or response.amount is None or float(response.amount) <= 0:
                actual_taken = 0.0
            else:
                harvest_amount = float(response.amount)
                actual_taken = self.pool.fish(harvest_amount)
                agent.add_resources(actual_taken)

            if self.verbose:
                limit_warn = f"(limit={self.leader_limit}, penalty={float(response.amount or harvest_amount) - self.leader_limit:.1f} over)" if (self.leader_limit is not None and harvest_amount > self.leader_limit) else ""
                print(f"[sim]       {agent.name}: take {actual_taken:.1f} fish (pool now {self.pool.amount:.1f}) {limit_warn}")
            self._harvested_this_round[agent.id] = actual_taken
            self._total_harvested += actual_taken

            penalty_info = None
            pool_before = resources_before.get("pool", 0)
            pool_after = self.pool.amount if self.pool else 0
            agent.add_log_entry(
                round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
                type="harvest",
                data={"amount": actual_taken, "pool_before": pool_before, "pool_after": pool_after,
                      "limit": self.leader_limit, "violation": penalty_info is not None},
            )
            for other in self.agent_list:
                if other.id != agent.id and actual_taken > 0:
                    other.add_log_entry(
                        round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
                        type="pool_state",
                        data={"pool_before": pool_before, "pool_after": pool_after, "amount": actual_taken},
                    )

            if self.leader_limit is not None:
                penalty = calculate_penalty(
                    harvest_amount=actual_taken, limit=self.leader_limit,
                    penalty_rate=self.leader_penalty_rate or 0,
                )
                if penalty > 0:
                    self._violations_count += 1
                    distribute_fine(
                        penalty_amount=penalty, violator=agent, leader=self.leader,
                        pool=self.pool, destination=self.config["leader"]["fine_destination"],
                        non_violators=[a for a in self.agent_list if a.id != agent.id],
                    )
                    enforcer = self.leader.id if self.leader else "default"
                    penalty_info = {"imposed_by": enforcer, "amount": penalty, "destination": self.config["leader"]["fine_destination"]}
                    self._penalties_this_round[agent.id] = penalty_info
                    agent.violations += 1
                    self._total_penalties_amount += penalty
                    agent.add_log_entry(round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
                        type="penalty",
                        data={"text": f"You were penalized {penalty:.1f} fish for exceeding the {self.leader_limit:.1f} limit"})
                    if self.leader:
                        self.leader.add_log_entry(round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
                            type="system",
                            data={"text": f"You penalized {agent.name} {penalty:.1f} fish for exceeding the limit"})

            resources_after = {agent.id: agent.resources, "pool": self.pool.amount if self.pool else 0}
            self.recorder.record_event(
                turn=self.turn_counter, agent=agent.id, action="fish",
                amount=actual_taken, reasoning=response.reasoning,
                resources_before=resources_before, resources_after=resources_after,
                leader_limit=self.leader_limit, penalty=penalty_info,
            )

    def _build_harvest_context(self, agent: Agent) -> str:
        """Build the harvest prompt using prompts.py template."""
        leader_name = self._get_leader_name()

        return build_harvest_prompt(
            agent_name=agent.name,
            resources=agent.resources,
            round_num=self.current_round,
            leader_name=leader_name,
            limit=self.leader_limit,
            penalty_rate=self.leader_penalty_rate,
            pool_status=self._pool_status(),
            personality=agent.personality,
            memory_context=self._build_memory_context(agent),
        )

    def _record_round_metrics(self) -> None:
        """Record metrics for the current round."""
        total_harvest = sum(self._harvested_this_round.values())

        # Simple Gini coefficient calculation
        resources = [a.resources for a in self.agent_list]
        gini = self._calculate_gini(resources)

        # Network centrality -- who talks to whom
        centrality = self._compute_degree_centrality()

        self.recorder.record_round_metrics(
            total_harvest=total_harvest,
            pool_remaining=self.pool.amount if self.pool else 0,
            gini_coefficient=gini,
            violations=self._violations_count,
            penalties_imposed=self._violations_count,
            centrality=centrality,
        )

        # Build structured round history for agent prompts
        election = self._election_data or {}
        winner = election.get("winner")
        winner_name = self.agents.get(winner, Agent(id=winner, name=winner, resources=0)).name if winner else "None"
        harvest_detail = {a.name: self._harvested_this_round.get(a.id, 0) for a in self.agent_list}
        self._round_history.append({
            "round": self.current_round,
            "winner": winner_name,
            "winner_votes": election.get("votes", {}).get(winner, 0) if winner else 0,
            "harvest": harvest_detail,
            "total_harvest": total_harvest,
            "leader": self._get_leader_name(),
            "leader_limit": self.leader_limit,
            "leader_penalty": self.leader_penalty_rate,
        })

    def _compute_degree_centrality(self) -> dict[str, float]:
        """Compute degree centrality from conversation_log.

        For each agent, measures what fraction of other agents they
        communicated with (either sending or receiving messages).
        Higher values = more socially connected.
        """
        n = len(self.agent_list)
        if n <= 1:
            return {a.id: 0.0 for a in self.agent_list}

        # Track unique communication partners per agent
        partners: dict[str, set[str]] = {a.id: set() for a in self.agent_list}

        for entry in self.conversation_log:
            sender = entry.get("agent")
            if not sender:
                continue
            # Add recipients based on action type
            if entry.get("message"):
                if entry.get("is_private"):
                    # Private: targets are included
                    targets = entry.get("targets")
                    if targets is None and entry.get("target"):
                        targets = [entry["target"]]
                    if targets:
                        for tid in targets:
                            if tid and tid in partners:
                                partners[sender].add(tid)
                                partners[tid].add(sender)
                else:
                    # Public: everyone hears
                    for a in self.agent_list:
                        if a.id != sender:
                            partners[sender].add(a.id)

        # Normalize by (n-1) possible partners
        return {aid: len(contacts) / (n - 1) for aid, contacts in partners.items()}

    @staticmethod
    def _calculate_gini(values: list[float]) -> float:
        """Calculate the Gini coefficient for a list of values.

        0 = perfect equality, 1 = perfect inequality.
        """
        if not values or sum(values) == 0:
            return 0.0

        sorted_values = sorted(values)
        n = len(sorted_values)
        cumulative = 0
        for i, v in enumerate(sorted_values, start=1):
            cumulative += i * v

        gini = (2 * cumulative) / (n * sum(sorted_values)) - (n + 1) / n
        return max(0.0, min(1.0, gini))

    # ── memory: round summaries ─────────────────────────────────────

    def _build_round_summary(self, round_num: int) -> None:
        """Build a detailed summary of the just-completed round."""
        total_harvest = sum(self._harvested_this_round.values())
        pool_end = self.pool.amount

        agent_results = {}
        for agent in self.agent_list:
            harvested = self._harvested_this_round.get(agent.id, 0)
            violated = False
            penalty = self._penalties_this_round.get(agent.id)
            if self.leader_limit is not None:
                violated = harvested > self.leader_limit
            agent_results[agent.id] = {
                "harvested": harvested,
                "violated": violated,
                "penalty": penalty["amount"] if penalty else 0,
                "penalty_destination": penalty["destination"] if penalty else None,
            }

        leader_name = self.leader.name if self.leader else None

        summary = {
            "round": round_num,
            "leader": leader_name,
            "leader_platform": {
                "harvest_limit": self.leader_limit,
                "penalty_rate": self.leader_penalty_rate,
            } if self.leader else None,
            "election": self._election_data,
            "total_harvested": total_harvest,
            "pool_start": self._pool_start,
            "pool_end": pool_end,
            "agent_results": agent_results,
        }

        # Generate LLM summary
        summary_text = self._summarize_round(summary)
        summary["llm_summary"] = summary_text

        self.round_summaries.append(summary)

        # Store in each agent's memory
        for agent in self.agent_list:
            agent.add_memory(
                turn=self.turn_counter,
                type="round_summary",
                content=summary_text,
                significance="round_summary",
                emotional_impact="neutral",
            )

    def _summarize_round(self, summary: dict) -> str:
        """Ask the LLM to generate a concise round summary."""
        prompt = self._build_summary_prompt(summary)
        return self.llm.summarize(prompt)

    def _build_summary_prompt(self, summary: dict) -> str:
        """Build a prompt asking the LLM to summarize the round."""
        rnd = summary["round"]
        leader = summary.get("leader", "None")
        pool_s = summary["pool_start"]
        pool_e = summary["pool_end"]
        platform = summary.get("leader_platform")

        lines = [
            "Summarize what happened this round in 2-3 sentences. Key facts:",
            f"Leader: {leader}",
        ]
        if platform:
            lines.append(f"Leader platform: limit={platform['harvest_limit']}, penalty_rate={platform['penalty_rate']}")
        lines.append(f"Pool: {pool_s:.0f} -> {pool_e:.0f} fish")
        lines.append("Agent harvests:")
        for aid, ar in summary["agent_results"].items():
            name = self.agents.get(aid, None)
            name_str = name.name if name else aid
            flags = []
            if ar.get("violated"):
                flags.append(f"VIOLATED (penalty={ar.get('penalty', 0):.0f} fish to {ar.get('penalty_destination', '?')})")
            flag_str = " " + " ".join(flags) if flags else ""
            lines.append(f"  - {name_str}: {ar['harvested']:.0f} fish{flag_str}")

        # Include conversation highlights (last few messages)
        if self.conversation_log:
            recent = self.conversation_log[-6:]
            lines.append("Recent conversation:")
            for entry in recent:
                aide = entry["agent"]
                a = self.agents.get(aide, None)
                name_str = a.name if a else aide
                lines.append(f"  [{name_str}]: \"{entry['message']}\"")

        return "\n".join(lines)

    def _set_recorder_metadata(self) -> None:
        """Populate recorder with round summaries, agent memories, and personal logs."""
        # Agent memories as dicts
        memories: dict[str, list[dict]] = {}
        for agent in self.agent_list:
            memories[agent.id] = [
                {"turn": m.turn, "type": m.type, "content": m.content, "significance": m.significance}
                for m in agent.memories
            ]
        self.recorder.set_agent_memories(memories)

        # Personal logs for each agent
        personal_logs: dict[str, list[dict]] = {}
        for agent in self.agent_list:
            personal_logs[agent.id] = list(agent.personal_log)
        self.recorder.set_personal_logs(personal_logs)

        # Round summaries (minus llm_summary to avoid duplication)
        summaries_for_output: list[dict] = []
        for s in self.round_summaries:
            entry = dict(s)
            # Include the LLM summary in a compact form
            summaries_for_output.append(entry)
        self.recorder.set_round_summaries(summaries_for_output)

        # Conversation analysis results (significance labels per round)
        if self._analysis_results:
            self.recorder.set_analysis_results(self._analysis_results)
    def _call_reflections(self) -> None:
        """Generate personal reflections for each agent after a round.

        LLM calls in parallel, memory writes sequentially.
        """
        # Phase 1: Build prompts + call LLM in parallel
        reflection_results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.agent_list)) as ex:
            def _reflect(a):
                harvested = self._harvested_this_round.get(a.id, 0)
                leader_name = self.leader.name if self.leader else "None"
                violated = False
                penalty_msg = ""
                if self.leader_limit is not None:
                    violated = harvested > self.leader_limit
                if violated:
                    penalty_amt = self._penalties_this_round.get(a.id, {}).get("amount", 0)
                    penalty_msg = f" You violated the limit and paid a penalty of {penalty_amt:.0f} fish."

                vote_record = None
                for entry in reversed(a.personal_log):
                    if entry.get("type") == "vote" and entry.get("round") == self.current_round:
                        vote_record = entry.get("data", {})
                        break

                prompt = build_reflection_prompt(
                    agent_name=a.name, round_num=self.current_round,
                    harvested=harvested, penalty_msg=penalty_msg,
                    leader_name=leader_name, resources=a.resources,
                    vote_record=vote_record, personality=a.personality,
                )
                try:
                    return a.id, self.llm.reflect(prompt)
                except Exception:
                    return a.id, []

            futures = {ex.submit(_reflect, a): a for a in self.agent_list}
            for f in concurrent.futures.as_completed(futures):
                aid, reflections = f.result()
                reflection_results[aid] = reflections

        # Phase 2: Store memories sequentially
        for agent in self.agent_list:
            for mem in reflection_results.get(agent.id, []):
                if isinstance(mem, dict) and mem.get("content"):
                    agent.add_memory(
                        turn=self.turn_counter,
                        type="reflection",
                        content=mem["content"],
                        significance=mem.get("significance", "personal"),
                        emotional_impact=mem.get("emotional_impact", "neutral"),
                    )

    def _analyze_conversation(self) -> None:
        """Post-hoc analysis: ask a separate LLM call to label conversation significance.

        Writes labels (alliance/collusion/betrayal/deal) to self._analysis_results.
        These labels are for the RECORDER output and the VISUALIZER only.
        They are NOT injected into agent prompts.
        """
        # Only analyze talk events (skip pass/fish/transfer)
        talk_entries = [
            e for e in self.conversation_log
            if e.get("message") and e.get("action") in ("public_talk", "private_talk", "talk")
        ]
        if not talk_entries:
            return

        try:
            labels = self.llm.analyze(talk_entries)
            if labels:
                self._analysis_results.update(labels)
        except Exception:
            pass  # Analysis failures are non-critical