"""Shared fixtures for all tests."""

import pytest


@pytest.fixture
def default_agent_names():
    return ["Alice", "Bob", "Charlie"]


@pytest.fixture
def default_config():
    return {
        "simulation": {"num_rounds": 1, "turns_per_phase": 3},
        "agents": {
            "names": ["Alice", "Bob", "Charlie"],
            "starting_resources": 50.0,
        },
        "resources": {
            "carrying_capacity": 100.0,
            "regeneration_factor": 1.5,
        },
        "leader": {
            "fine_destination": "common_pool",
        },
        "election": {
            "method": "plurality",
            "elections_every_round": False,
        },
    }
