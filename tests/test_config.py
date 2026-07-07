"""Tests for configuration loading, defaults, and merging.

Phase 6 — TDD Layer 1: pure logic, no LLM.
Tests 22-23 from the specification.
"""

import pytest
from simulation.config import load_config, load_config_from_yaml, deep_merge, validate_config, DEFAULT_CONFIG


class TestConfig:
    """Tests 22-23: Config loading and overrides."""

    def test_config_defaults(self):
        """Test 22: Empty config returns defaults."""
        config = load_config({})
        assert config["simulation"]["num_rounds"] == DEFAULT_CONFIG["simulation"]["num_rounds"]
        assert config["simulation"]["turns_per_phase"] == DEFAULT_CONFIG["simulation"]["turns_per_phase"]
        assert config["agents"]["starting_resources"] == DEFAULT_CONFIG["agents"]["starting_resources"]
        assert config["resources"]["carrying_capacity"] == DEFAULT_CONFIG["resources"]["carrying_capacity"]
        assert config["leader"]["fine_destination"] == DEFAULT_CONFIG["leader"]["fine_destination"]
        assert config["election"]["method"] == DEFAULT_CONFIG["election"]["method"]

    def test_config_override_simulation(self):
        """Test 23: User config overrides specific simulation fields."""
        user_config = {
            "simulation": {
                "num_rounds": 10,
                "turns_per_phase": 5,
            }
        }
        config = load_config(user_config)
        assert config["simulation"]["num_rounds"] == 10
        assert config["simulation"]["turns_per_phase"] == 5
        # Other fields remain default
        assert config["agents"]["starting_resources"] == DEFAULT_CONFIG["agents"]["starting_resources"]

    def test_config_override_agents(self):
        """Override agent names and starting resources."""
        user_config = {
            "agents": {
                "names": ["Alice", "Bob"],
                "starting_resources": 100.0,
            }
        }
        config = load_config(user_config)
        assert config["agents"]["names"] == ["Alice", "Bob"]
        assert config["agents"]["starting_resources"] == 100.0

    def test_config_override_leader(self):
        """Override leader settings."""
        user_config = {
            "leader": {
                "fine_destination": "leader_stash",
            }
        }
        config = load_config(user_config)
        assert config["leader"]["fine_destination"] == "leader_stash"

    def test_config_override_election(self):
        """Override election settings."""
        user_config = {
            "election": {
                "elections_every_round": False,
            }
        }
        config = load_config(user_config)
        assert config["election"]["elections_every_round"] is False

    def test_config_missing_section_adds_defaults(self):
        """If a whole section is missing, defaults are filled in."""
        config = load_config({"simulation": {"num_rounds": 2}})
        # Agents section should have defaults
        assert "agents" in config
        assert "leader" in config
        assert "resources" in config

    def test_config_validate_invalid_fine_destination(self):
        """Invalid fine destination should raise."""
        with pytest.raises(ValueError):
            load_config({"leader": {"fine_destination": "invalid"}})

    def test_config_validate_negative_rounds(self):
        """Negative rounds should raise."""
        with pytest.raises(ValueError):
            load_config({"simulation": {"num_rounds": -1}})

    def test_config_validate_zero_rounds(self):
        """Zero rounds should raise."""
        with pytest.raises(ValueError):
            load_config({"simulation": {"num_rounds": 0}})

    def test_deep_merge_top_level(self):
        """deep_merge merges top-level keys."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_deep_merge_nested(self):
        """deep_merge merges nested dicts recursively."""
        base = {"simulation": {"num_rounds": 4, "turns_per_phase": 10}}
        override = {"simulation": {"num_rounds": 8}}
        result = deep_merge(base, override)
        assert result["simulation"]["num_rounds"] == 8
        assert result["simulation"]["turns_per_phase"] == 10  # Preserved from base

    def test_deep_merge_overwrite_non_dict(self):
        """deep_merge overwrites non-dict values, doesn't merge them."""
        base = {"agents": ["Alice", "Bob"]}
        override = {"agents": ["Charlie"]}
        result = deep_merge(base, override)
        assert result["agents"] == ["Charlie"]  # Overwritten, not merged

    def test_deep_merge_does_not_mutate_inputs(self):
        """deep_merge creates a new dict, doesn't modify inputs."""
        base = {"a": 1}
        override = {"b": 2}
        result = deep_merge(base, override)
        assert base == {"a": 1}  # Unchanged
        assert override == {"b": 2}  # Unchanged
        assert result is not base

    def test_validate_config_custom_election_method(self):
        """Config allows custom election method."""
        config = load_config({"election": {"method": "plurality"}})
        assert config["election"]["method"] == "plurality"

    def test_elections_every_round_default(self):
        """elections_every_round defaults to True."""
        config = load_config({})
        assert config["election"]["elections_every_round"] is True

    def test_candidacy_cost_default(self):
        """candidacy_cost defaults to 5.0."""
        config = load_config({})
        assert config["leader"]["candidacy_cost"] == 5.0

    def test_config_override_elections_every_round(self):
        """Override elections_every_round to False."""
        config = load_config({"election": {"elections_every_round": False}})
        assert config["election"]["elections_every_round"] is False

    def test_config_override_candidacy_cost(self):
        """Override candidacy_cost."""
        config = load_config({"leader": {"candidacy_cost": 2.0}})
        assert config["leader"]["candidacy_cost"] == 2.0


class TestConfigFiles:
    """Tests for YAML config file loading."""

    def test_five_agents_drama_loads(self):
        """five_agents_drama.yaml loads without error and has correct values."""
        config = load_config_from_yaml("config/five_agents_drama.yaml")
        assert config["simulation"]["num_rounds"] == 3
        assert config["simulation"]["turns_per_phase"] == 10
        assert len(config["agents"]["names"]) == 5
        assert config["agents"]["starting_resources"] == 20.0
        assert config["leader"]["default_penalty_rate"] == 0.5
        assert config["leader"]["candidacy_cost"] == 5.0
        assert config["election"]["elections_every_round"] is True

    def test_collapse_test_yaml_loads(self):
        """collapse_test.yaml loads without error."""
        config = load_config_from_yaml("config/collapse_test.yaml")
        assert config["election"]["elections_every_round"] is True
        assert config["leader"]["candidacy_cost"] == 2.0

    def test_invite_test_yaml_loads(self):
        """invite_test.yaml loads without error."""
        config = load_config_from_yaml("config/invite_test.yaml")
        assert config["election"]["elections_every_round"] is True
        assert config["leader"]["candidacy_cost"] == 2.0
