"""LLM abstraction layer — interface, StubLLM, and response models.

The engine never calls DeepSeek directly. It calls LLMInterface methods.
StubLLM provides deterministic responses for testing.
"""

from __future__ import annotations

import random
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMResponse:
    """Parsed response from an LLM decision call."""

    action: str  # "public_talk" | "private_talk" | "fish" | "pass" | "transfer" | ...
    target: Optional[str] = None
    targets: Optional[list[str]] = None
    message: Optional[str] = None
    amount: Optional[float] = None
    group: Optional[str] = None  # channel name for talk action (default "public")
    reasoning: str = ""


@dataclass
class CampaignPlatform:
    """A candidate's election platform."""

    harvest_limit: float
    penalty_rate: float
    message: str = ""
    reasoning: str = ""


class LLMInterface(ABC):
    """Abstract interface for LLM decision-making.

    The engine calls these methods; subclasses implement the actual
    LLM calls (or return stubbed responses in tests).
    """

    @abstractmethod
    def decide(self, prompt: str) -> LLMResponse:
        ...

    @abstractmethod
    def campaign(self, prompt: str) -> CampaignPlatform:
        ...

    @abstractmethod
    def vote(self, prompt: str) -> str:
        """Return the agent_id of the candidate the agent votes for."""
        ...

    @abstractmethod
    def reflect(self, prompt: str) -> list[dict]:
        """Return list of new memories."""
        ...

    @abstractmethod
    def summarize(self, prompt: str) -> str:
        """Generate a free-form text summary. Returns raw text."""
        ...

    @abstractmethod
    def analyze(self, conversations: list[dict]) -> dict[int, str]:
        """Analyze a conversation log and assign significance labels.

        Takes a list of conversation entries (each with turn, agent, message, etc.)
        and returns a dict mapping turn_number -> significance_label.

        Labels: null | "small_talk" | "alliance" | "collusion" | "betrayal" | "deal"

        This is a post-hoc assessment — a separate LLM call labels each interaction
        independently, unlike self-assessment where the agent labels its own behavior.
        """
        ...

    def stats(self) -> dict:
        """Return usage statistics (calls, tokens, time).

        Default empty dict for LLMs that don't track stats.
        """
        return {}


class StubLLM(LLMInterface):
    """Returns pre-scripted responses for deterministic testing.

    Each call returns the next response in the list, cycling if needed.
    Thread-safe for parallel use.
    """

    def __init__(self, responses: list[dict] = None):
        self.responses = responses or []
        self.call_count = 0
        self._stub_lock = threading.Lock()

    def _next(self) -> dict:
        """Get the next response, cycling if exhausted (thread-safe)."""
        if not self.responses:
            return {"action": "pass", "reasoning": "No stub response configured"}
        with self._stub_lock:
            idx = self.call_count % len(self.responses)
            self.call_count += 1
            return self.responses[idx]

    def decide(self, prompt: str) -> LLMResponse:
        r = self._next()
        return LLMResponse(
            action=r.get("action", "pass"),
            target=r.get("target"),
            targets=r.get("targets"),
            message=r.get("message"),
            amount=r.get("amount"),
            group=r.get("group"),
            reasoning=r.get("reasoning", ""),
        )

    def campaign(self, prompt: str) -> CampaignPlatform:
        r = self._next()
        return CampaignPlatform(
            harvest_limit=r.get("harvest_limit", 5.0),
            penalty_rate=r.get("penalty_rate", 1.0),
            message=r.get("message", ""),
            reasoning=r.get("reasoning", ""),
        )

    def vote(self, prompt: str) -> str:
        r = self._next()
        return r.get("vote_for", "")

    def reflect(self, prompt: str) -> list[dict]:
        """Stub reflect — returns empty memories.

        Does NOT consume from the response list (like summarize),
        so tests don't need to account for reflection calls.
        """
        return []

    def summarize(self, prompt: str) -> str:
        """Stub summarize — always returns a fixed default.

        Does NOT consume from the response list (unlike decide/campaign/vote),
        so tests don't need to account for summary calls in their stub scripts.
        """
        return "Agents discussed resource management."

    def analyze(self, conversations: list[dict]) -> dict[int, str]:
        """Stub analyze — returns empty labels (no significance detected).

        Does NOT consume from the response list.
        """
        return {}

    def stats(self) -> dict:
        """Stub stats — no usage tracked."""
        return {}

    def reset(self) -> None:
        """Reset the call counter."""
        self.call_count = 0


class RecordingLLM(LLMInterface):
    """Wraps another LLM and records all prompts and responses.

    Useful for debugging and snapshot testing.
    """

    def __init__(self, inner: LLMInterface):
        self.inner = inner
        self.history: list[dict] = []

    def decide(self, prompt: str) -> LLMResponse:
        response = self.inner.decide(prompt)
        self.history.append({"prompt": prompt, "response": response})
        return response

    def campaign(self, prompt: str) -> CampaignPlatform:
        response = self.inner.campaign(prompt)
        self.history.append({"prompt": prompt, "response": response})
        return response

    def vote(self, prompt: str) -> str:
        response = self.inner.vote(prompt)
        self.history.append({"prompt": prompt, "response": response})
        return response

    def reflect(self, prompt: str) -> list[dict]:
        response = self.inner.reflect(prompt)
        self.history.append({"prompt": prompt, "response": response})
        return response

    def summarize(self, prompt: str) -> str:
        response = self.inner.summarize(prompt)
        self.history.append({"prompt": prompt, "response": response})
        return response

    def analyze(self, conversations: list[dict]) -> dict[int, str]:
        response = self.inner.analyze(conversations)
        self.history.append({"prompt": conversations, "response": response})
        return response

    def stats(self) -> dict:
        """Delegate to inner LLM's stats."""
        return self.inner.stats()
