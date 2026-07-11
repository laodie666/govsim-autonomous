"""Configuration loading, defaults, and validation for GovSim Autonomous.

Supports YAML files and dict-based overrides.
"""

from __future__ import annotations

import copy
from typing import Any

from simulation.leader import VALID_DESTINATIONS

DEFAULT_CONFIG: dict[str, Any] = {
    "simulation": {
        "num_rounds": 4,
        "turns_per_phase": 10,
    },
    "agents": {
        "names": ["Alice", "Bob", "Charlie", "Diana", "Eve"],
        "starting_resources": 50.0,
        "personalities": {},  # Optional: agent_name -> personality string
    },
    "resources": {
        "carrying_capacity": 100.0,
        "regeneration_factor": 2.0,
        "fish_per_harvest": 5.0,
    },
    "leader": {
        "fine_destination": "leader_stash",
        "default_limit": 10.0,
        "default_penalty_rate": 0.0,
        "candidacy_cost": 25.0,
    },
    "election": {
        "method": "plurality",
        "elections_every_round": True,
    },
    "llm": {
        "provider": "deepseek",
        "model": "deepseek-chat",
        "temperature": 0.7,
        "max_tokens": 500,
        "base_url": "https://api.deepseek.com",
    },
    "output": {
        "format": "json",
        "include_full_transcripts": True,
        "include_agent_memories": True,
    },
}


def deep_merge(base: dict, override: dict) -> dict:
    """Deep merge two dictionaries. override values take precedence."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def validate_config(config: dict) -> None:
    """Validate config values and raise on invalid input."""
    sim = config.get("simulation", {})
    if sim.get("num_rounds", 1) < 1:
        raise ValueError(f"num_rounds must be >= 1, got {sim.get('num_rounds')}")

    leader = config.get("leader", {})
    dest = leader.get("fine_destination", "common_pool")
    if dest not in VALID_DESTINATIONS:
        raise ValueError(
            f"Invalid fine_destination: '{dest}'. "
            f"Valid: {', '.join(sorted(VALID_DESTINATIONS))}"
        )


def load_config(user_config: dict | None = None) -> dict:
    """Load configuration, merging user overrides into defaults.

    Args:
        user_config: Optional dict with user-specified overrides.

    Returns:
        A complete config dict with defaults filled in.

    Raises:
        ValueError: If config values are invalid.
    """
    config = deep_merge(DEFAULT_CONFIG, user_config or {})
    validate_config(config)
    return config


def load_config_from_yaml(path: str) -> dict:
    """Load configuration from a YAML file.

    Args:
        path: Path to the YAML config file.

    Returns:
        A complete config dict with defaults filled in.
    """
    import yaml

    with open(path) as f:
        user_config = yaml.safe_load(f)
    return load_config(user_config or {})
