# GovSim-Autonomous

Multi-agent LLM-driven common-pool fishery simulation. Agents fish a shared lake over multiple rounds while an elected leader sets harvest policy. Agents can use private channels to lobby, bribe, form coalitions, and negotiate — designed to produce emergent strategic behavior like vote-buying, coalition formation, betrayal, and defection.

---

## Simulation Design

The core idea: the leader's power to set harvest limit + penalty rate creates an implicit market for policy influence. Agents can bribe the leader, form coalitions to control elections, or defect for short-term gain. Every round:

1. **Pre-election free interaction** — Agents form private channels, negotiate deals, trade votes
2. **Election** — Candidates campaign on policy platforms, secret ballot, winner's policy is enforced
3. **Harvest** — Agents decide how many fish to take; violators are penalized
4. **Post-harvest** — Debrief, accountability, planning for next round
5. **Reflection** — Each agent produces subjective free-text reflection

Penalties and fines are configurable (common pool, leader stash, redistribute, or destroyed). The lake regenerates between rounds but **collapses permanently** if overfished below 0.01.

---

## Requirements

```bash
pip install openai pyyaml pytest
```

Optionally for coverage: `pip install pytest-cov`

## API Key

Requires a DeepSeek API key. Set it as an environment variable:

```bash
$env:DEEPSEEK_API_KEY = "sk-..."
```

To use a different OpenAI-compatible provider, modify `simulation/llm_client.py` line ~68 to change `base_url` and set the appropriate API key.

Run with `--stub` for deterministic simulation without any API calls.

## Quick Start

```bash
# Run with stub first (deterministic, no API calls)
python -m simulation.main --config config/personalities_run.yaml --stub --verbose

# Set API key and run with real LLM
$env:DEEPSEEK_API_KEY = "sk-..."
python -m simulation.main --config config/personalities_run.yaml --seed 42 --verbose

# Run with full prompt recording (writes prompts to separate debug file)
python -m simulation.main --config config/personalities_run.yaml --seed 42 --record-prompts
```

## Flags

| Flag | Description |
|---|---|
| `--config`, `-c` | Path to YAML config file |
| `--seed`, `-s` | Random seed for reproducibility |
| `--stub` | Use StubLLM instead of DeepSeek (no API calls) |
| `--verbose`, `-v` | Print per-turn actions during simulation |
| `--record-prompts` | Save full prompt text + LLM responses to `<run_id>_prompts.json` |
| `--output`, `-o` | Output JSON path (default: `outputs/<run_id>.json`) |
| `--run-id`, `-r` | Custom run identifier |
| `--dry-run` | Print config and exit without running |

## Config

Configs are YAML files in `config/`. See `config/personalities_run.yaml` for the full drama setup:

```yaml
simulation:
  num_rounds: 3
  turns_per_phase: 8          # turns x agents = LLM calls per phase
agents:
  names: [Sage, River, Ash, Quinn, Kai]
  starting_resources: 30.0
  personalities:               # injected as behavioral directives
    Sage: "You are a long-term thinker..."
resources:
  carrying_capacity: 200.0
  regeneration_factor: 2.0
leader:
  fine_destination: destroyed   # common_pool, leader_stash, redistribute, destroyed
  default_limit: 6.0
  default_penalty_rate: 1.0
  candidacy_cost: 5.0
election:
  method: plurality
  elections_every_round: true
```

## Running Tests

```bash
# All tests
python -m pytest tests/ -v

# Integration tests only
python -m pytest tests/test_integrated_pipeline.py -v

# With coverage
pip install pytest-cov
python -m pytest tests/ --cov=simulation
```

332 tests, all passing.

## Project Structure

```
simulation/          # Core engine
├── engine.py        # Orchestrator: rounds, phases, action dispatch
├── prompts.py       # User prompt templates (dynamic state only)
├── llm_client.py    # DeepSeek client + system prompts + _extract_json
├── llm_interface.py # Abstract interface, StubLLM, RecordingLLM
├── channels.py      # Channel manager, invitations, dissolution
├── agent.py         # Agent state: resources, memories, personal log
├── config.py        # Config loading, merging, validation
├── election.py      # Vote tallying
├── leader.py        # Penalty calculation, fine distribution
├── recorder.py      # Output JSON construction
├── resource_pool.py # Pool dynamics, regeneration, collapse
└── main.py          # CLI entry point
tests/               # 332 tests
config/              # YAML configs
outputs/             # Simulation output JSON
```

## Output

The main output JSON contains:
- Full turn-by-turn event log (agent, action, message, reasoning, resources before/after)
- Personal logs per agent (everything they saw/heard/did)
- Agent memories (reflections, round summaries)
- Election results, penalties, pool state
- Metrics (gini coefficient, total harvest, violations)

With `--record-prompts`, a separate `<run_id>_prompts.json` is saved containing the full prompt text and LLM response for every single call — useful for debugging what the agent actually saw.
