# GovSim-Autonomous — Agent Reference

> **Purpose:** Single source of truth for implementer agents working on govsim-autonomous. Current state after Phase 7: 332 tests passing, prompt system/user split, personality-driven agents, full prompt recording.

---

## 1. Project Overview

**GovSim-Autonomous** is a multi-agent LLM-driven common-pool fishery simulation. Five agents (Sage, River, Ash, Quinn, Kai) fish a shared lake over multiple rounds while a leader sets harvest policy (limit + penalty rate). Agents use private channels to lobby, bribe, form coalitions, and negotiate. Designed to produce **interesting emergent dynamics** — vote-buying, coalition formation, betrayal, and strategic defection.

**Tech stack:**
- Python 3.11+
- pytest 7.x (332 tests)
- DeepSeek LLM via OpenAI-compatible SDK
- YAML configs via `pyyaml`
- Plain dataclasses, no async, no web framework

**Design by:** Jinesis

---

## 2. File Map

### 2.1 `simulation/` — Core engine

```
simulation/
├── engine.py           (~1550 lines) Main orchestrator, phase handlers, turn dispatch
├── agent.py            Agent dataclass: resources, memories, personal_log
├── actions.py          Transfer validation and execution
├── channels.py         ChannelManager: private groups, invitations, dissolution
├── config.py           DEFAULT_CONFIG, load_config(), deep_merge()
├── election.py         tally_election() — plurality with tie-breaking
├── leader.py           calculate_penalty(), distribute_fine()
├── llm_interface.py    Abstract LLMInterface, StubLLM, RecordingLLM, dataclasses
├── llm_client.py       DeepSeekLLM — real API, _extract_json, **system prompts**
├── prompts.py          **User prompt templates** — dynamic state only
├── main.py             CLI entry point with argparse, --record-prompts
├── recorder.py         Event recording, output JSON, personal logs, channel snapshots
└── resource_pool.py    ResourcePool — fish(), regenerate(), collapse detection
```

### 2.2 `tests/` — 332 tests

```
tests/
├── test_integrated_pipeline.py  # 30 integration tests: prompt content, end-to-end scenarios, penalty paths
├── test_engine_unit.py          # Engine integration tests (election, harvest, channels, transfers)
├── test_engine_multi_round.py   # Multi-round state persistence, leader transitions
├── test_engine_collapse.py      # Pool collapse detection
├── test_engine_personal_log.py  # Personal log wiring for all event types
├── test_channels.py             # Channel unit tests + edge cases (14 new)
├── test_llm_client.py           # _extract_json edge cases, plain number fix
├── test_llm_interface.py        # StubLLM, RecordingLLM, prompt serialization
├── test_prompts.py              # Prompt builder tests (updated for system/user split)
├── test_v2_features.py          # V2 feature tests (heard_by, candidacy, dissolution)
└── ...                          # Plus unit tests per module
```

### 2.3 `config/` — YAML configuration

| File | Purpose |
|---|---|
| `personalities_run.yaml` | **Recommended** — 5 agents (Sage, River, Ash, Quinn, Kai), 3 rounds, 8 turns, personalities, elections every round |
| `five_agents_drama.yaml` | Legacy drama config (John, Kate, Jack, Emma, Luke) |
| `five_agents.yaml` | Legacy sandbox (4 agents, no penalty) |
| `collapse_test.yaml` | Pool collapse test config |
| `invite_test.yaml` | Channel invitation test config |
| `small_test.yaml` | Small fast test config |

---

## 3. Architecture

### 3.1 Prompt Architecture (Current)

The prompt is split across **system** and **user** messages:

**System prompt** (static, ~760 chars, in `llm_client.py`):
- World rules (lake regenerates, collapse at < 0.01, leader sets policy)
- All available actions with channel visibility rules
- JSON response format

**User prompt** (dynamic, 300-700 chars, in `prompts.py`):
- Identity: `"You are Sage. Round 1, free interaction."`
- State: `"Your fish: 30.0 | Lake: 200/200 | Leader: Sage (limit=10, penalty=2x)"`
- Phase context: `"An election follows this phase. After that: harvest."`
- Last action: `"Your last action: talk: 'I propose a limit of 10'"`
- Memory: channel group + members, personal log with `[public]`/`[channel]` tags, reflections

### 3.2 Prompt Types

| Function | Used For | Key Content |
|---|---|---|
| `build_decision_prompt` | Free interaction (pre & post) | Identity, state, phase context, last action, memory |
| `build_campaign_prompt` | Election campaign | Candidate identity, resources, opponents list, memory |
| `build_vote_prompt` | Voting | Voter identity, candidate platforms table, memory |
| `build_harvest_prompt` | Harvest | Identity, state, leader policy, memory |
| `build_reflection_prompt` | Reflection (post-round) | Round data, vote record, harvested amount |

### 3.3 Round Flow

```
Round N:
  1. Pre-election free_interaction  (turns_per_phase turns)
     - Phase context: "An election follows this phase. After that: harvest."
     - Agents talk, create groups, transfer fish, lobby for votes
     - Channels dissolve at end
  2. Election phase
     a. Campaign: each candidate states platform (limit, penalty_rate, message)
     b. Voting: secret ballot — only totals public, individual votes invisible
     c. Winner's platform becomes policy
     Channels dissolve at end
  3. Harvest phase (sequential per agent)
     - Each agent decides how many fish to take
     - Penalty applied if over leader's limit
     - Pool collapse check (if pool < 0.01, game ends)
     Channels dissolve at end
  4. Post-harvest free_interaction
     - Phase context: "Discuss what happened and plan for next round."
     Channels dissolve at end
  5. Reflection phase
     - Each agent produces free-text reflection + plan (type="reflection" memories)
     - Injected into next round's prompt as "--- YOUR REFLECTIONS ---"
```

### 3.4 Visibility Rules

| Info | Visible to whom |
|---|---|
| Public talk messages | All agents |
| Private channel messages | Only channel members |
| Transfers in public channel | All agents |
| Transfers in private channel | Only channel members |
| Campaign platforms | All agents |
| Vote totals (candidate: count) | All agents |
| Individual votes | **Only the voter** (in personal log) |
| Who left/returned to public | All remaining public members |
| Penalties imposed | All agents (harvest events show amounts) |
| Personal logs | Only the owning agent |
| Leader identity + policy | All agents |

---

## 4. Current State (Phase 7)

### 4.1 Bug fixes deployed

| # | Bug | Fixed in |
|---|---|---|
| 1 | `group` field not parsed by DeepSeek client | `llm_client.py:136` |
| 2 | `_execute_talk()` and `_execute_talk_channel()` no-op stubs | Deleted |
| 3 | No `fish` action dispatch in free interaction | `engine.py:370-379` |
| 4 | Harvest phase ignores `action` field | `engine.py:1064-1066` (skip if pass/0) |
| 5 | Dead `Action`/`ActionType` enum | Deleted from `actions.py` |
| 6 | Greedy JSON regex `r'\{.*\}'` → non-greedy `r'\{.*?\}'` | `llm_client.py:38` |
| 7 | Pool collapse threshold `== 0` → `< 0.01` | `engine.py:241` |
| 8 | NameError in harvest verbose path (uninit `harvest_amount`) | `engine.py:1073` |
| 9 | **`decide()` crashes on plain number** (harvest LLM returns `5` not JSON) | `llm_client.py:131-136` |

### 4.2 Key features added (Phase 3-7)

| Feature | Where |
|---|---|
| **System/user prompt split** | `llm_client.py` (system prompts), `prompts.py` (user prompts only) |
| **`[public]` / `[channel]` conversation log tags** | `engine.py:_format_log_entry` |
| **"Your last action"** self-awareness in prompts | `engine.py:_describe_agent_action`, `prompts.py` |
| **Phase context sentences** | `engine.py:_phase_context`, `prompts.py` |
| **"X left public" / "X returned to public" notifications** | `engine.py:_execute_create_group/accept_invite/leave_group` |
| **`--record-prompts` flag** | `main.py`, saves full prompt/response pairs to separate debug file |
| **Personality-driven agents** | `config/personalities_run.yaml`, injected via `agent.personality` |
| **Penalty destinations** (`leader_stash`, `redistribute`, `destroyed`) | `leader.py:distribute_fine`, tested end-to-end |
| **`_extract_json` edge case handling** | `llm_client.py:_extract_json` — fences, nested, arrays, plain numbers |
| **332 tests** (from 258) | All passing |

### 4.3 Action aliases

```python
# engine.py:94-121
_ACTION_ALIASES = {
    "speak": "public_talk", "talk": "talk", "public_talk": "public_talk",
    "private_talk": "private_talk", "dm": "private_talk", "whisper": "private_talk",
    "create_group": "create_group", "create_channel": "create_group", "form_group": "create_group",
    "accept_invite": "accept_invite", "join": "accept_invite",
    "reject_invite": "reject_invite", "decline": "reject_invite",
    "leave_group": "leave_group", "leave": "leave_group",
    "transfer": "transfer", "send": "transfer", "give": "transfer",
    "fish": "fish", "harvest": "fish", "catch": "fish",
    "pass": "pass", "skip": "pass", "idle": "pass",
    "nominate": "nominate", "vote": "vote",
}
```

---

## 5. Test Patterns

### 5.1 StubLLM — main test helper

```python
from simulation.llm_interface import StubLLM

stub = StubLLM([
    {"action": "pass", "reasoning": "."},
    {"action": "fish", "amount": 5.0, "reasoning": "."},
])
```

**Important:** `StubLLM.reflect()`, `summarize()`, and `analyze()` do NOT consume from the response list. Only `decide()`, `campaign()`, and `vote()` consume.

### 5.2 RecordingLLM — prompt capture

```python
from simulation.llm_interface import RecordingLLM

rec = RecordingLLM(inner_llm)
engine = Engine(config, llm=rec)
engine.run()

# Inspect prompts
for entry in rec.history:
    print(entry["prompt"])        # The full prompt string
    print(entry["response"])      # LLMResponse, CampaignPlatform, or str
```

Used in `test_integrated_pipeline.py` to verify prompt content contains expected game state.

### 5.3 Counting responses for a round

With `elections_every_round=True`, `N` agents, `T` turns_per_phase:

```
free:     N × T   decide() calls
campaign: N       campaign() calls
vote:     N       vote() calls
harvest:  N       decide() calls
post:     N × T   decide() calls
Total:   N × (2T + 3)  calls per round
```

StubLLM cycles when exhausted — always provide enough responses or handle wrap.

### 5.4 Direct agent turn control (for channel tests)

```python
engine._reset_round_state()
engine.current_round = 1
engine.current_phase = "free_interaction"
engine.recorder.start_round(1)
engine.recorder.start_phase("free_interaction")

engine.llm = StubLLM([{"action": "create_group", "targets": ["bob"], ...}])
engine.turn_counter += 1
engine._handle_agent_turn(alice)
```

This avoids shuffled-order unpredictability. Used in `test_channel_creation_and_private_talk_privacy`.

---

## 6. Common Gotchas

### 6.1 Harvest plain number (FIXED — DO NOT REVERT)

The LLM returns a plain number (`8`) instead of JSON during harvest. The `decide()` method now checks `isinstance(data, (int, float))` and converts to `LLMResponse(action="fish", amount=float(data))`.

### 6.2 Prompt split is intentional

World rules, available actions, and JSON format are in the **system prompt** (`llm_client.py`). The **user prompt** (`prompts.py`) contains only dynamic state. Do not add action lists or format instructions to the user prompt.

### 6.3 `[public]` tag is always shown

Every talk log entry now has a channel tag. `[public]` for public messages, `[channel_N]` for private messages. The `_format_log_entry` function in `engine.py` controls this.

### 6.4 "Left public" / "returned to public"

Logged automatically when agents create groups, accept invites, or leave groups. Not logged for `dissolve_all` (phase transitions).

### 6.5 Personalities are injected as-is

The `personalities` field in config is stored on `Agent.personality` and injected as `"Personality: {text}"` in prompts. There's no validation — put whatever directive text you want (behavioral instructions, roleplay descriptions, etc.).

### 6.6 Fine destination affects collapse dynamics

- `common_pool`: Penalty fish return to lake — softens collapse
- `destroyed`: Penalty fish vanish — collapse is more likely
- `leader_stash`: Leader collects fines — creates bribery incentive
- `redistribute`: Non-violators split the fine — rewards compliance

### 6.7 No candidacy cost enforcement in engine (yet)

The engine deducts `candidacy_cost` from candidates. All agents are candidates by default. If an agent can't afford it, they're skipped. No-candidate fallback uses `default_limit` + `default_penalty_rate`.

---

## 7. Quick Reference

```bash
# Run
python -m simulation.main --config config/personalities_run.yaml --seed 42 --verbose

# Run with prompt recording
python -m simulation.main --config config/personalities_run.yaml --seed 42 --record-prompts

# Run with stub (test without API)
python -m simulation.main --config config/personalities_run.yaml --stub --verbose

# Run all tests
python -m pytest tests/ -v

# Run integration tests
python -m pytest tests/test_integrated_pipeline.py -v

# Run with coverage
python -m pytest tests/ --cov=simulation -v
```

### Key config: `config/personalities_run.yaml`

- 5 agents with distinct behavioral personalities
- 3 rounds, 8 turns per phase
- 200 carrying capacity, 2x regeneration
- Elections every round, 5-fish candidacy cost
- Penalties go to common pool

### Output files

- `<run_id>.json` — Main output (turns, personal logs, memories, metrics)
- `<run_id>_prompts.json` — With `--record-prompts`: every prompt + response
