"""Election mechanics — simple plurality voting with tie-breaking.

Pure logic: no LLM involvement, fully deterministic given a seed.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field


class ElectionError(Exception):
    """Raised when an election cannot be completed."""


VALID_METHODS = {"plurality"}


@dataclass
class ElectionResult:
    """The outcome of an election."""

    winner: str
    vote_counts: dict[str, int] = field(default_factory=dict)
    total_votes: int = 0
    tie_broken: bool = False


def tally_election(
    votes: list[str],
    method: str = "plurality",
    seed: int | None = None,
) -> ElectionResult:
    """Tally votes and determine the winner using the specified election method.

    Args:
        votes: List of agent IDs representing each vote cast.
        method: Election method — only "plurality" is currently supported.
        seed: Random seed for deterministic tie-breaking.

    Returns:
        ElectionResult with winner, vote counts, and tie-breaking info.

    Raises:
        ElectionError: If no votes are cast.
        ValueError: If the election method is unsupported.
    """
    if method not in VALID_METHODS:
        raise ValueError(
            f"Unsupported election method: '{method}'. Valid: {', '.join(sorted(VALID_METHODS))}"
        )

    if not votes:
        raise ElectionError("Cannot hold an election with zero votes.")

    vote_counts = dict(Counter(votes))

    if method == "plurality":
        max_votes = max(vote_counts.values())
        top_candidates = [c for c, v in vote_counts.items() if v == max_votes]

        if len(top_candidates) == 1:
            winner = top_candidates[0]
            tie_broken = False
        else:
            # Tie-break: randomly pick among tied candidates
            rng = random.Random(seed)
            winner = rng.choice(top_candidates)
            tie_broken = True

        return ElectionResult(
            winner=winner,
            vote_counts=vote_counts,
            total_votes=len(votes),
            tie_broken=tie_broken,
        )

    # Future methods would go here

    raise ValueError(f"Unimplemented election method: '{method}'")
