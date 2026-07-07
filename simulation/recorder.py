"""Event recording and output formatting for GovSim Autonomous.

Produces a structured JSON output designed for the visualizer.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Optional


@dataclass
class EventOutput:
    """A single turn/event in the simulation."""

    turn: int
    agent: str
    action: str
    target: Optional[str] = None
    targets: Optional[list[str]] = None
    is_private: bool = False
    message: Optional[str] = None
    amount: Optional[float] = None
    reasoning: str = ""
    significance: Optional[str] = None
    group: Optional[str] = None  # channel name for talk actions
    heard_by: Optional[list[str]] = None  # agents who heard this talk
    resources_before: Optional[dict[str, float]] = None
    resources_after: Optional[dict[str, float]] = None
    leader_limit: Optional[float] = None
    penalty: Optional[dict] = None


@dataclass
class PhaseOutput:
    """A phase within a round (free_interaction, election, harvesting, etc.)."""

    phase: str
    turns: list[dict] = field(default_factory=list)
    result: Optional[dict] = None  # Election result, harvest result, etc.


@dataclass
class RoundOutput:
    """A single round of the simulation."""

    round: int
    phases: list[dict] = field(default_factory=list)


class Recorder:
    """Records simulation events and produces the final output JSON."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self._rounds: list[dict] = []
        self._current_round: Optional[dict] = None
        self._current_phase: Optional[dict] = None
        self._metrics_by_round: list[dict] = []
        self._round_summaries: list[dict] = []
        self._agent_memories: dict[str, list[dict]] = {}
        self._analysis_results: dict[int, str] = {}
        self._personal_logs: dict[str, list[dict]] = {}
        self._started_at: float = time.time()
        self._config: dict = {}
        self._end_condition: str = "time_limit"
        self._collapsed_at_round: int | None = None
        self._survival_length: int = 0
        self._prompt_log: list[dict] | None = None

    def set_end_condition(
        self,
        end_condition: str,
        collapsed_at_round: int | None = None,
        survival_length: int = 0,
    ) -> None:
        """Set the end condition metadata."""
        self._end_condition = end_condition
        self._collapsed_at_round = collapsed_at_round
        self._survival_length = survival_length

    def set_config(self, config: dict) -> None:
        """Store the simulation config for output."""
        self._config = config

    def start_round(self, round_num: int) -> None:
        """Begin a new round."""
        self._current_round = {
            "round": round_num,
            "phases": [],
        }
        self._rounds.append(self._current_round)
        self._current_phase = None

    def start_phase(self, phase_name: str) -> None:
        """Begin a new phase within the current round."""
        if self._current_round is None:
            raise RuntimeError("Cannot start phase without starting a round first")
        self._current_phase = {
            "phase": phase_name,
            "turns": [],
        }
        # If this is an election phase, add result placeholder
        if phase_name == "election":
            self._current_phase["result"] = None
        self._current_round["phases"].append(self._current_phase)

    def record_event(
        self,
        turn: int,
        agent: str,
        action: str,
        target: Optional[str] = None,
        targets: Optional[list[str]] = None,
        is_private: bool = False,
        message: Optional[str] = None,
        amount: Optional[float] = None,
        reasoning: str = "",
        significance: Optional[str] = None,
        group: Optional[str] = None,
        heard_by: Optional[list[str]] = None,
        resources_before: Optional[dict] = None,
        resources_after: Optional[dict] = None,
        leader_limit: Optional[float] = None,
        penalty: Optional[dict] = None,
    ) -> None:
        """Record a single turn/event in the current phase."""
        if self._current_phase is None:
            raise RuntimeError("Cannot record event without starting a phase first")

        event = EventOutput(
            turn=turn,
            agent=agent,
            action=action,
            target=target,
            targets=targets,
            is_private=is_private,
            message=message,
            amount=amount,
            reasoning=reasoning,
            significance=significance,
            group=group,
            heard_by=heard_by,
            resources_before=resources_before or {},
            resources_after=resources_after or {},
            leader_limit=leader_limit,
            penalty=penalty,
        )
        self._current_phase["turns"].append(asdict(event))

    def record_vote(self, voter: str, candidate: str) -> None:
        """Record a single vote (stored as an event in the election phase)."""
        self.record_event(
            turn=len(self._current_phase["turns"]) + 1,
            agent=voter,
            action="vote",
            target=candidate,
            reasoning="",
        )

    def record_election_result(
        self,
        winner: str,
        votes: dict[str, int],
        voter_map: dict[str, str],
        acceptance_message: Optional[str] = None,
    ) -> None:
        """Record the election result."""
        if self._current_phase is not None and self._current_phase["phase"] == "election":
            self._current_phase["result"] = {
                "winner": winner,
                "votes": votes,
                "voter_map": voter_map,
                "acceptance_message": acceptance_message,
            }

    def record_round_metrics(
        self,
        total_harvest: float = 0.0,
        pool_remaining: float = 0.0,
        gini_coefficient: float = 0.0,
        violations: int = 0,
        penalties_imposed: int = 0,
        centrality: Optional[dict[str, float]] = None,
    ) -> None:
        """Record end-of-round metrics."""
        round_num = self._current_round["round"] if self._current_round else len(self._rounds) + 1
        entry: dict[str, Any] = {
            "round": round_num,
            "total_harvest": total_harvest,
            "pool_remaining": pool_remaining,
            "gini_coefficient": gini_coefficient,
            "violations": violations,
            "penalties_imposed": penalties_imposed,
        }
        if centrality:
            entry["centrality"] = centrality
        self._metrics_by_round.append(entry)

    def set_round_summaries(self, summaries: list[dict]) -> None:
        """Store round summaries (LLM-generated)."""
        # Remove llm_summary field to avoid duplication; it's in round_summaries
        self._round_summaries = summaries

    def set_agent_memories(self, memories: dict[str, list[dict]]) -> None:
        """Store per-agent memories for output."""
        self._agent_memories = memories

    def set_analysis_results(self, results: dict[int, str]) -> None:
        """Store conversation analysis results (significance labels)."""
        self._analysis_results = results

    def set_channel_snapshot(self, snapshot: dict[str, list[str]]) -> None:
        """Record the current channel state for this phase."""
        if self._current_phase is not None:
            self._current_phase["channel_states"] = snapshot

    def set_personal_logs(self, logs: dict[str, list[dict]]) -> None:
        """Store per-agent personal logs for output."""
        self._personal_logs = logs

    def get_output(self) -> dict:
        """Get the complete simulation output as a dict."""
        output: dict[str, Any] = {
            "run_id": self.run_id,
            "config": self._config,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self._started_at)),
            "end_condition": self._end_condition,
            "collapsed_at_round": self._collapsed_at_round,
            "survival_length": self._survival_length,
            "rounds": self._rounds,
            "metrics": {
                "by_round": self._metrics_by_round,
            },
        }
        if self._round_summaries:
            output["round_summaries"] = self._round_summaries
        if self._agent_memories:
            output["agent_memories"] = self._agent_memories
        if self._analysis_results:
            output["analysis"] = self._analysis_results
        if self._personal_logs:
            output["personal_logs"] = self._personal_logs
        if self._prompt_log:
            output["prompt_log"] = self._prompt_log
        return output

    def to_json(self, indent: int = 2) -> str:
        """Serialize the output to JSON."""
        return json.dumps(self.get_output(), indent=indent)

    def save(self, path: str) -> None:
        """Save the output to a JSON file."""
        with open(path, "w") as f:
            f.write(self.to_json())
