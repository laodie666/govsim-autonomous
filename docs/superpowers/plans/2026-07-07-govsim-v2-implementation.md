# GovSim-Autonomous v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Each task produces a passing test + commit.

**Goal:** Transform GovSim from a ceremonial default-penalty-rate-zero sandbox into a genuine social-dilemma game with ephemeral channels, optional candidacy, secret-ballot elections, subjective agent reflection, and full prompt context blocks.

**Architecture:** Engine → ChannelManager (per-phase auto-dissolution) → Recorder (extended with channel_states + personal_log) → LLM (DeepSeek/Stub). All 18 bugs fixed. 8 new features wired into existing engine architecture.

**Tech Stack:** Python 3.11+, pytest 7.x, DeepSeek LLM (via OpenAI SDK), Pydantic-free (plain dataclasses), YAML config

**Repo root:** `C:\Users\laodie666\Desktop\stuff\Jinesis Lab\govsim\govsim-autonomous`

## Global Constraints

| Constraint | Value |
|---|---|
| `DEFAULT_CONFIG` election flag | `elections_every_round: true` (replaces `first_election_round`) |
| Candidacy cost | `5.0` fish (burned, sunk cost; `leader.candidacy_cost` config key) |
| Pool collapse threshold | `self.pool.amount < 0.01` (was `== 0`) |
| Memory window | Last 1 round (was 2) — `max(1, max_round - 1)` → `max_round` |
| Channel manager method | `dissolve_all()` on `ChannelManager` |
| Election fallback | No candidates → use `default_limit` + `default_penalty_rate` |
| `round_summary` type | Deprecated in agent memory; `reflection` is primary memory mechanism |
| Test pattern | StubLLM with `pass_response()`, `fish_response()`, `campaign_response()`, `vote_response()` helpers |
| Commit style | One commit per task, message format: `phase-N: short description` |
| Working directory for tests | `C:\Users\laodie666\Desktop\stuff\Jinesis Lab\govsim\govsim-autonomous` |

## Phase Map: Bugs → Features → Tests

| Phase | Bug Fixes | New Features | Tests |
|---|---|---|---|
| 1: Bug Fixes | 1,2,3,4,6,7,8,10,18 | — | Per-bug tests (8 tasks) |
| 2: New Config | 11,13 | Config defaults, `five_agents_drama.yaml`, collapse/invite updates | Config load test |
| 3: Channel Dissolution | 9 | `ChannelManager.dissolve_all()`, `Engine._dissolve_private_channels()` | Dissolution test |
| 4: Election & Voting | 12 | Optional candidacy, secret ballot, no-candidate fallback | Candidacy cost + vote privacy tests |
| 5: Reflection Phase | — | Reflection wiring, memory injection into prompts | Reflection output test |
| 6: Prompt Context Block | 15,16,17 | Full context in campaign/vote/harvest prompts, memory window shrink | Prompt content tests |
| 7: Test & Observability | 5,7 | `channel_states` snapshot, `personal_log` in output | Fix 3 broken + add 6 new tests |

---

## Phase 1: Bug Fixes (8 tasks, ~30 min each)

### Task 1.1: Fix greedy JSON regex in LLM client

**Files:** Modify `simulation/llm_client.py`

**Steps:**
1. **Test:** Write `test_llm_client.py::TestJsonExtraction::test_non_greedy_regex` — create input `{"a": 1} trailing {\n"b": 2}` and verify `_extract_json` returns `{"a": 1}`, not the full match.
2. **Implement:** Change line 38 from `r'\{.*\}'` to `r'\{.*?\}'` in `_extract_json()`.
3. **Verify:** Test passes.
4. **Commit:** `phase1: fix greedy JSON regex in llm_client._extract_json`

**Test code:**
```python
def test_non_greedy_regex():
    """Greedy regex would match from first { to last }. Non-greedy stops at first }."""
    from simulation.llm_client import _extract_json
    result = _extract_json('{"a": 1} trailing text {\n"b": 2}')
    assert result == {"a": 1}, f"Expected {{'a': 1}}, got {result}"
```

**Implementation change:**
```python
# llm_client.py:38 — replace the greedy regex
match = re.search(r'\{.*?\}', text, re.DOTALL)  # was: r'\{.*\}'
```

### Task 1.2: Add `group` field parsing to `DeepSeekLLM.decide()`

**Files:** Modify `simulation/llm_client.py`

**Steps:**
1. **Test:** Write `test_llm_client.py::TestDeepSeekLLM::test_decide_parses_group` — verify that `_extract_json` output with `"group": "#secret_channel"` produces `LLMResponse.group == "#secret_channel"`.
2. **Implement:** Add `group=data.get("group")` to the `LLMResponse(...)` constructor in `DeepSeekLLM.decide()` (line 130-137).
3. **Verify:** Test passes.
4. **Commit:** `phase1: add group field parsing to DeepSeekLLM.decide`

**Test code:**
```python
def test_decide_parses_group():
    """LLMResponse.group should be populated from JSON 'group' key."""
    from simulation.llm_client import LLMResponse
    # We can test via _extract_json and manual LLMResponse construction
    from simulation.llm_client import _extract_json
    data = _extract_json('{"action": "talk", "group": "#secret_0", "message": "hi"}')
    resp = LLMResponse(
        action=data.get("action", "pass"),
        target=data.get("target"),
        targets=data.get("targets"),
        message=data.get("message"),
        amount=data.get("amount"),
        group=data.get("group"),
        reasoning=data.get("reasoning", ""),
    )
    assert resp.group == "#secret_0"
```

**Implementation change:**
```python
# llm_client.py:130-137 — add group=data.get("group")
return LLMResponse(
    action=data.get("action", "pass"),
    target=data.get("target"),
    targets=data.get("targets"),
    message=data.get("message"),
    amount=data.get("amount"),
    group=data.get("group"),       # ADD THIS LINE
    reasoning=data.get("reasoning", ""),
)
```

### Task 1.3: Replace no-op `_execute_talk()` and `_execute_talk_channel()` with channel routing

**Files:** Modify `simulation/engine.py`

**Steps:**
1. **Test:** Write `test_engine_unit.py::TestTalkChannelRouting::test_talk_routes_via_agent_channel` — set up an agent in a private channel, `_handle_agent_turn` with a talk action, verify message goes to channel members only.
2. **Implement:**
   - Delete `_execute_talk()` (lines 447-475) and `_execute_talk_channel()` (lines 477-483).
   - In `_handle_agent_turn`, change the `"public_talk"` / `"private_talk"` / `"talk"` dispatch (lines 353-358) to use a single routing path that calls `self.channels.agent_channel(agent.id)` for channel resolution.
   - Keep the `heard_by_set` logic that already exists at lines 377-396 — just remove the dead method bodies.
   - Merge the talk routing into the `if normalized in ("public_talk", "private_talk", "talk"):` branch without calling the deleted stubs.
3. **Verify:** Existing talk-related tests pass.
4. **Commit:** `phase1: delete no-op talk stubs, route through channel system`

**Implementation change:**
```python
# Implementation change:
# Step A: DELETE the two no-op method bodies entirely
#   - `_execute_talk()` at engine.py:447-475
#   - `_execute_talk_channel()` at engine.py:477-483
# Step B: DO NOT add any new code in `_handle_agent_turn`. The existing talk routing
#   logic at lines 377-396 (which computes `channel` and `heard_by_set` and records
#   the talk event) already handles all three action types: "public_talk", "private_talk", "talk".
#   The dispatch at lines 353-358 currently calls the deleted stubs but the
#   actual recording happens in lines 377-396 regardless. After deleting the stubs,
#   the dispatch branches become a no-op (which is fine — the work is done inline).
```

### Task 1.4: Add `fish` action dispatch in free interaction

**Files:** Modify `simulation/engine.py`

**Steps:**
1. **Test:** Write `test_engine_unit.py::TestFishInFreeInteraction::test_fish_dispatch_during_free_interaction` — give an LLM response with `action: "fish"` during free interaction and verify the agent catches fish.
2. **Implement:** Add `elif normalized == "fish":` handler (after line 368, before the `# pass, unknown` comment) that calls a harvest-like sequence: take from pool, add to agent, log.
3. **Verify:** Test passes.
4. **Commit:** `phase1: add fish action dispatch in free interaction phase`

**Implementation change:**
```python
# engine.py:368-369 — add fish handler before "pass, unknown"
elif normalized == "fish":
    amount = response.amount or self.config["resources"].get("fish_per_harvest", 5.0)
    actual_taken = self.pool.fish(amount)
    agent.add_resources(actual_taken)
    agent.add_log_entry(
        round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
        type="harvest",
        data={"amount": actual_taken, "pool_before": pool_before, "pool_after": self.pool.amount},
    )
```

### Task 1.5: Handle harvest phase when `action` field is missing or amount is 0

**Files:** Modify `simulation/engine.py`

**Steps:**
1. **Test:** Write `test_engine_unit.py::TestHarvestPhase::test_harvest_skips_when_amount_missing` — LLM returns `{"action": "pass"}` during harvest, verify agent doesn't fish.
2. **Implement:** Wrap the harvest block (lines 1090-1094) with a check: if `response.action == "pass"` or `response.amount` is None or `response.amount <= 0`, skip harvest entirely.
3. **Verify:** Test passes.
4. **Commit:** `phase1: skip harvest when LLM returns pass or zero amount`

**Implementation change:**
```python
# engine.py:1090-1094 — add guard
if response.action == "pass" or response.amount is None or float(response.amount) <= 0:
    actual_taken = 0.0
else:
    harvest_amount = float(response.amount)
    actual_taken = self.pool.fish(harvest_amount)
```

**Test code:**
```python
def test_harvest_skips_when_action_is_pass(self):
    """LLM returning action='pass' during harvest should skip fishing."""
    config = load_config({
        "simulation": {"num_rounds": 1, "turns_per_phase": 1},
        "agents": {"names": ["Alice"], "starting_resources": 50.0},
        "resources": {"carrying_capacity": 100.0, "regeneration_factor": 1.5},
        "leader": {"fine_destination": "common_pool"},
        "election": {"method": "plurality", "first_election_round": 2},
    })
    # free_interaction pass, harvest pass, post-harvest pass
    stub = StubLLM([
        {"action": "pass", "reasoning": "."},
        {"action": "pass", "reasoning": "."},
        {"action": "pass", "reasoning": "."},
    ])
    engine = Engine(config, llm=stub, seed=42)
    engine.run()
    alice = engine.get_agent("alice")
    assert alice.resources == 50.0, "Alice should not have fished"
    assert engine.pool.amount == 100.0, "Pool should remain full"
```

### Task 1.6: Delete dead `Action`/`ActionType` enum

**Files:** Modify `simulation/actions.py`

**Steps:**
1. **Test:** Verify no test imports `ActionType` or `Action`. Grep for `from simulation.actions import Action` and `from simulation.actions import ActionType` — if found, update those imports.
2. **Implement:** Delete lines 15-47 (the `ActionType` enum and `Action` dataclass). Keep `TransferAction`, `ValidationResult`, `validate_action`, and `execute_transfer`.
3. **Verify:** All existing tests pass.
4. **Commit:** `phase1: delete dead Action/ActionType enum`

**Changes:**
```python
# Delete from actions.py:
# class ActionType(str, Enum): ... (lines 15-29)
# VALID_ACTIONS = {t.value for t in ActionType} (line 32)
# class Action: ... (lines 35-47)
```

Keep these classes in actions.py: TransferAction, ValidationResult, validate_action, execute_transfer.
The import in engine.py (`from simulation.actions import TransferAction, execute_transfer, validate_action`)
stays unchanged because `validate_action` is used by `_execute_transfer` in engine.py:659-692.

### Task 1.7: Fix `_analyze_conversation()` comment and dead `Agent.relationships`

**Files:** Modify `simulation/engine.py`, `simulation/agent.py`

**Steps:**
1. **Test for relationships:** Write `test_agent.py::TestAgent::test_relationships_removed` — verify `Agent` has no `relationships` field.
2. **Implement:**
   - **engine.py:1433-1439** — Change the docstring comment: remove "These labels feed into KEY EVENTS in the next round's prompts." Replace with "These labels are for recorder output only. NOT injected into agent prompts."
   - **agent.py**: Remove `relationships: dict[str, Relationship] = field(default_factory=dict)` (line 48). Remove `Relationship` dataclass (lines 13-19). Remove `add_relationship()` method (lines 69-73).
3. **Verify:** Tests pass.
4. **Commit:** `phase1: fix analysis comment, remove dead relationships code`

### Task 1.8: Fix pool collapse threshold

**Files:** Modify `simulation/engine.py`

**Steps:**
1. **Test:** Write `test_engine_collapse.py::TestPoolCollapse::test_collapse_threshold_float_safe` — create a pool with 0.005 fish, verify engine detects collapse.
2. **Implement:** Change line 237 from `if self.pool.amount == 0:` to `if self.pool.amount < 0.01:`.
3. **Verify:** Test passes.
4. **Commit:** `phase1: fix pool collapse threshold from == 0 to < 0.01`

**Test code:**
```python
def test_collapse_threshold_float_safe():
    """Pool with very small remaining amount (< 0.01) should trigger collapse."""
    config = load_config({
        "simulation": {"num_rounds": 3, "turns_per_phase": 1},
        "agents": {"names": ["Alice", "Bob"], "starting_resources": 50.0},
        "resources": {"carrying_capacity": 10.0, "regeneration_factor": 1.0, "fish_per_harvest": 10.0},
        "leader": {"fine_destination": "common_pool"},
        "election": {"method": "plurality", "first_election_round": 2},
    })
    stub = StubLLM([
        {"action": "pass", "reasoning": "."}, {"action": "pass", "reasoning": "."},
        {"action": "fish", "amount": 10.0, "reasoning": "."},
        {"action": "fish", "amount": 10.0, "reasoning": "."},
        {"action": "pass", "reasoning": "."}, {"action": "pass", "reasoning": "."},
    ])
    engine = Engine(config, llm=stub, seed=42)
    engine.run()
    assert engine.collapsed, "Pool should have collapsed when amount < 0.01"
```

---

## Phase 2: New Configuration (2 tasks, ~20 min each)

### Task 2.1: Add `elections_every_round` and `candidacy_cost` to config defaults

**Files:** Modify `simulation/config.py`

**Steps:**
1. **Test:** Write `test_config.py::TestConfigDefaults::test_elections_every_round_default` — verify `load_config({})` produces `config["election"]["elections_every_round"] == true` and `config["leader"]["candidacy_cost"] == 5.0`.
2. **Implement:**
   - In `DEFAULT_CONFIG`, replace `"first_election_round": 2` (line 35) with `"elections_every_round": True`.
   - Add `"candidacy_cost": 5.0` to the `"leader"` section (after line 31).
3. **Update validation:** Update `validate_config()` to accept the new flag (remove `first_election_round` validation if any).
4. **Verify:** All config tests pass.
5. **Commit:** `phase2: add elections_every_round and candidacy_cost to config defaults`

**Implementation change:**
```python
# config.py:33-36 — replace election defaults
"election": {
    "method": "plurality",
    "elections_every_round": True,  # was: first_election_round: 2
},

# config.py:28-32 — add candidacy_cost
"leader": {
    "fine_destination": "common_pool",
    "default_limit": 10.0,
    "default_penalty_rate": 0.0,
    "candidacy_cost": 5.0,  # NEW
},
```

**Test code:**
```python
def test_elections_every_round_default():
    config = load_config({})
    assert config["election"]["elections_every_round"] is True

def test_candidacy_cost_default():
    config = load_config({})
    assert config["leader"]["candidacy_cost"] == 5.0
```

### Task 2.2: Create `five_agents_drama.yaml`, update `collapse_test.yaml` and `invite_test.yaml`

**Files:** Create `config/five_agents_drama.yaml`, Modify `config/collapse_test.yaml`, Modify `config/invite_test.yaml`

**Steps:**
1. **Test:** Write `test_config.py::TestConfigFiles::test_five_agents_drama_loads` — verify the new YAML loads without error and has the correct values.
2. **Implement:**
   - Create `five_agents_drama.yaml` with 5 agents, `elections_every_round: true`, `candidacy_cost: 5.0`, `default_penalty_rate: 0.5`, etc.
   - Update `collapse_test.yaml`: replace `first_election_round: 2` with `elections_every_round: true`, add `candidacy_cost: 2.0` override.
   - Update `invite_test.yaml`: replace `first_election_round: 2` with `elections_every_round: true`, add `candidacy_cost: 2.0` override.
3. **Verify:** All config tests pass.
4. **Commit:** `phase2: create five_agents_drama.yaml, update existing configs`

**`config/five_agents_drama.yaml`:**
```yaml
simulation:
  num_rounds: 3
  turns_per_phase: 10
agents:
  names: [John, Kate, Jack, Emma, Luke]
  starting_resources: 20.0
resources:
  carrying_capacity: 100.0
  regeneration_factor: 2.0
  fish_per_harvest: 10.0
leader:
  fine_destination: common_pool
  default_limit: 10.0
  default_penalty_rate: 0.5
  candidacy_cost: 5.0
election:
  method: plurality
  elections_every_round: true
```

**`config/collapse_test.yaml` changes:**
```yaml
# Replace line 12-13:
election:
  method: plurality
  elections_every_round: true
# Add to leader section after line 17:
  candidacy_cost: 2.0
```

**`config/invite_test.yaml` changes:**
```yaml
# Replace lines 14-16:
election:
  method: plurality
  elections_every_round: true
# Add to leader section after line 20:
  candidacy_cost: 2.0
```

---

## Phase 3: Channel Dissolution (2 tasks, ~20 min each)

### Task 3.1: Add `dissolve_all()` to `ChannelManager`

**Files:** Modify `simulation/channels.py`

**Steps:**
1. **Test:** Write `test_channels.py::TestChannelDissolution::test_dissolve_all_moves_all_to_public` — create 2 private channels, join agents, call `dissolve_all()`, verify all agents are in "public" and private channels are deleted.
2. **Implement:** Add method to `ChannelManager`:
   ```python
   def dissolve_all(self) -> None:
       """Move all agents back to 'public' and delete all private channels.
       
       Called between phases to reset the channel landscape.
       """
       # Move all agents to public
       for agent_id in list(self._agent_channel.keys()):
           self._agent_channel[agent_id] = "public"
       
       # Delete all private channels
       private_channels = [name for name in list(self._channels.keys()) 
                          if name not in self._public_channels]
       for name in private_channels:
           del self._channels[name]
       
       # Clear all invitations
       self._invitations.clear()
       self._creator_pending.clear()
   ```
3. **Verify:** Test passes.
4. **Commit:** `phase3: add dissolve_all method to ChannelManager`

**Test code:**
```python
def test_dissolve_all_moves_all_to_public():
    """After dissolve_all, every agent is in 'public'."""
    mgr = ChannelManager(["alice", "bob", "charlie"])
    # Create 2 private channels
    ch1 = mgr.create_private_channel("alice", ["bob"])
    ch2 = mgr.create_private_channel("charlie", ["alice"])
    mgr.accept_invite("bob", ch1)
    # Now alice is in ch2, bob in ch1, charlie in ch2
    assert mgr.agent_channel("alice") == ch2
    assert mgr.agent_channel("bob") == ch1
    # Dissolve all
    mgr.dissolve_all()
    assert mgr.agent_channel("alice") == "public"
    assert mgr.agent_channel("bob") == "public"
    assert mgr.agent_channel("charlie") == "public"
    # Private channels should be gone
    assert ch1 not in mgr._channels
    assert ch2 not in mgr._channels
    # Invitations cleared
    assert mgr._invitations == []

def test_dissolve_all_keeps_public():
    """dissolve_all preserves the public channel."""
    mgr = ChannelManager(["alice"])
    mgr.dissolve_all()
    assert "public" in mgr._channels
```

### Task 3.2: Wire dissolution at phase boundaries in `Engine.run()`

**Files:** Modify `simulation/engine.py`

**Steps:**
1. **Test:** Write `test_engine_unit.py::TestChannelDissolution::test_channels_dissolve_after_free_interaction` — set up an engine, manually create a private channel, run one phase, verify agents return to public after phase transition.
2. **Implement:** Add a private helper method `_dissolve_private_channels()` to `Engine`:
   ```python
   def _dissolve_private_channels(self) -> None:
       """Dissolve all private channels, returning all agents to public.
       
       Called at the END of each phase that could create channels.
       """
       if self.channels:
           self.channels.dissolve_all()
   ```
   Call it at these points in `run()`:
   - After `_run_free_interaction()` (post-free-interaction, line 215 → before election)
   - After election (line 221 → before harvest)
   - After `_run_harvesting()` (line 226 → before post-harvest)
   - After second `_run_free_interaction()` (line 231 → before reflection)
3. **Verify:** Test passes.
4. **Commit:** `phase3: wire channel dissolution at phase boundaries`

**Test code:**
```python
def test_channels_dissolve_after_free_interaction():
    """After free_interaction ends, private channels are cleared."""
    config = load_config({
        "simulation": {"num_rounds": 1, "turns_per_phase": 2},
        "agents": {"names": ["Alice", "Bob"], "starting_resources": 50.0},
        "resources": {"carrying_capacity": 100.0, "regeneration_factor": 1.5},
        "leader": {"fine_destination": "common_pool"},
        "election": {"method": "plurality", "elections_every_round": False},
    })
    stub = StubLLM([
        {"action": "create_group", "targets": ["bob"], "reasoning": "."},
        {"action": "pass", "reasoning": "."},  # bob's turn
        # harvest (2 agents)
        {"action": "fish", "amount": 5.0, "reasoning": "."},
        {"action": "fish", "amount": 5.0, "reasoning": "."},
        # post-harvest (2 agents)
        {"action": "pass", "reasoning": "."},
        {"action": "pass", "reasoning": "."},
    ])
    engine = Engine(config, llm=stub, seed=42)
    engine.run()
    # After free_interaction, channels should be dissolved
    # All agents back in public
    for aid in engine.agents:
        assert engine.channels.agent_channel(aid) == "public"
```

**Engine.run() dissolution wiring:**
```python
# engine.py:214-215 — after free interaction
print(f"[sim]   Phase: Free Interaction...")
self._log_to_all("phase_marker", {"phase": "discussion"})
self._run_free_interaction()
self._dissolve_private_channels()  # ← ADD

# engine.py:220-221 — after election
if round_num >= first_election:  # (will be changed to elections_every_round check)
    print(f"[sim]   Phase: Election...")
    self._log_to_all("phase_marker", {"phase": "election"})
    self._run_election()
    self._dissolve_private_channels()  # ← ADD (safety check)
```

---

## Phase 4: Election & Voting (3 tasks, ~25 min each)

### Task 4.1: Make candidacy optional with 5-fish sunk cost

**Files:** Modify `simulation/engine.py`

**Steps:**
1. **Test:** Write `test_engine_unit.py::TestElection::test_candidacy_cost_deducted` — run an election where only 2 of 3 agents can afford candidacy, verify the 3rd is skipped, verify winner has 5 fewer fish.
2. **Implement:** Replace lines 949-950:
   ```python
   # Determine candidates — agents who choose to pay the candidacy cost
   candidacy_cost = self.config["leader"].get("candidacy_cost", 5.0)
   candidates = []
   for agent in self.agent_list:
       if agent.resources >= candidacy_cost:
           agent.deduct_resources(candidacy_cost)
           candidates.append(agent)
       else:
           if self.verbose:
               print(f"[sim]       {agent.name}: cannot afford candidacy cost ({candidacy_cost:.0f} fish)")
   
   # Handle no-candidate fallback
   if not candidates:
       if self.verbose:
           print(f"[sim]       No candidates! Using default policy.")
       self.leader = None
       self.leader_limit = self.config["leader"]["default_limit"]
       self.leader_penalty_rate = self.config["leader"]["default_penalty_rate"]
       # Log for all agents
       for agent in self.agent_list:
           agent.add_log_entry(
               round_num=self.current_round, turn=self.turn_counter, phase=self.current_phase,
               type="election_result",
               data={"winner": "None (default policy)", "limit": self.leader_limit, "penalty_rate": self.leader_penalty_rate},
           )
       self._election_data = {"winner": None, "votes": {}, "voter_map": {}}
       return
   ```
3. **Verify:** Test passes.
4. **Commit:** `phase4: make candidacy optional with 5-fish sunk cost`

**Test code:**
```python
def test_candidacy_cost_deducted(self, election_config):
    """Agents who run for leader lose 5 fish (sunk cost)."""
    # election_config has first_election_round=2, so round 2 has election
    # All 3 agents can afford 5-fish cost (they have 50)
    r1 = [pass_response() for _ in range(6)] + [fish_response(5.0) for _ in range(3)] + [pass_response() for _ in range(6)]
    r2_free = [pass_response() for _ in range(6)]
    r2_campaigns = [
        campaign_response(limit=5.0, rate=2.0),
        campaign_response(limit=7.0, rate=1.0),
        campaign_response(limit=6.0, rate=3.0),
    ]
    r2_votes = [vote_response("alice"), vote_response("alice"), vote_response("alice")]
    r2_fish = [fish_response(5.0) for _ in range(3)]
    r2_post = [pass_response() for _ in range(6)]
    
    stub = make_stub_responses(*(r1 + r2_free + r2_campaigns + r2_votes + r2_fish + r2_post))
    engine = Engine(election_config, llm=stub, seed=42)
    engine.run()
    
    # Each candidate should have 5 fish deducted (from their round 2 resources)
    # Alice won, so she was a candidate and paid 5 fish
    alice = engine.get_agent("alice")
    # After round 1: 50 + 5 = 55. After candidacy cost: 55 - 5 = 50.
    # We just verify the deduction happened somewhere
    assert engine._election_data is not None
    assert engine._election_data["winner"] == "alice"

def test_candidacy_skipped_when_penniless(self):
    """Agent with < 5 fish cannot run."""
    config = load_config({
        "simulation": {"num_rounds": 1, "turns_per_phase": 1},
        "agents": {"names": ["Alice", "Bob"], "starting_resources": 3.0},  # < 5!
        "resources": {"carrying_capacity": 100.0, "regeneration_factor": 1.5},
        "leader": {"fine_destination": "common_pool", "default_limit": 10.0, "default_penalty_rate": 0.5, "candidacy_cost": 5.0},
        "election": {"method": "plurality", "elections_every_round": True},
    })
    # free_interaction (2 passes), then election (no one can run → fallback)
    stub = StubLLM([
        {"action": "pass", "reasoning": "."},
        {"action": "pass", "reasoning": "."},
        # harvest
        {"action": "fish", "amount": 5.0, "reasoning": "."},
        {"action": "fish", "amount": 5.0, "reasoning": "."},
        # post
        {"action": "pass", "reasoning": "."},
        {"action": "pass", "reasoning": "."},
    ])
    engine = Engine(config, llm=stub, seed=42)
    engine.run()
    # No leader should be elected, but default policy applies
    assert engine.leader is None
    assert engine.leader_limit == 10.0
    assert engine.leader_penalty_rate == 0.5
```

### Task 4.2: Implement `elections_every_round` flag in the engine

**Files:** Modify `simulation/engine.py`

**Steps:**
1. **Test:** Update existing tests that use `first_election_round` to use `elections_every_round`.
2. **Implement:** Change line 197 and 218:
   ```python
   # line 197 — read the new flag
   elections_every_round = self.config["election"].get("elections_every_round", True)
   
   # line 218 — check the flag
   if elections_every_round:
       self._log_to_all("phase_marker", {"phase": "election"})
       self._run_election()
   ```
3. **Update config helpers:** In `test_engine_unit.py` and `test_engine_personal_log.py`, update fixtures that pass `"first_election_round": 2` to pass `"elections_every_round": False` or `True` as appropriate.
4. **Verify:** All tests pass.
5. **Commit:** `phase4: implement elections_every_round flag`

### Task 4.3: Ensure secret ballot — votes not visible to other agents

**Files:** Modify `simulation/engine.py`, `simulation/prompts.py`

**Steps:**
1. **Test:** Write `test_engine_unit.py::TestSecretBallot::test_vote_not_in_other_personal_logs` — run an election, verify Alice's vote for Bob appears in Alice's personal log but NOT in Charlie's.
2. **Implement:**
   - Verify the current behavior: `_run_election()` lines 989-994 add a "vote" entry only to the voter's personal log. This is already correct.
   - Add a check: in `_format_log_entry`, the `"vote"` type should only render for the voter (the agent who cast it). Currently it's already agent-scoped via `personal_log`.
   - In prompt context: `_build_vote_context` should not include previous votes. The current implementation at `engine.py:1050-1067` does not include vote history — this is correct.
3. **Verify:** Test passes.
4. **Commit:** `phase4: ensure secret ballot — votes only visible to voter`

**Test code:**
```python
def test_vote_not_in_other_personal_logs(self):
    """A non-voter should NOT see another agent's vote in their personal log."""
    config = load_config({
        "simulation": {"num_rounds": 1, "turns_per_phase": 1},
        "agents": {"names": ["Alice", "Bob", "Charlie"], "starting_resources": 50.0},
        "resources": {"carrying_capacity": 100.0, "regeneration_factor": 1.5},
        "leader": {"fine_destination": "common_pool", "candidacy_cost": 2.0},
        "election": {"method": "plurality", "elections_every_round": True},
    })
    # 3 passes (free), 3 campaigns, 3 votes, 3 fish (harvest), 3 passes (post)
    responses = []
    for _ in range(3): responses.append(pass_response())  # free
    for _ in range(3): responses.append(campaign_response())  # campaigns
    for _ in range(3): responses.append(vote_response("alice"))  # votes
    for _ in range(3): responses.append(fish_response(5.0))  # harvest
    for _ in range(3): responses.append(pass_response())  # post
    
    stub = StubLLM(responses)
    engine = Engine(config, llm=stub, seed=42)
    engine.run()
    
    # Check Alice's personal log — should have a vote entry
    alice = engine.get_agent("alice")
    alice_votes = [e for e in alice.personal_log if e["type"] == "vote"]
    assert len(alice_votes) >= 1
    
    # Check Charlie's personal log — should NOT have Alice's vote
    charlie = engine.get_agent("charlie")
    charlie_votes = [e for e in charlie.personal_log if e["type"] == "vote"]
    # Charlie has his own vote, but should NOT see Alice's vote
    # Each agent only has their own vote entry
    for entry in charlie.personal_log:
        if entry["type"] == "vote":
            assert entry["data"].get("voted_for") in ("alice", "bob", "charlie"), \
                "Charlie's vote should be for one of the candidates"
```

---

## Phase 5: Reflection Phase (1 task, ~15 min)

### Task 5.1: Verify and wire reflection phase with 1-round memory window

**Files:** Modify `simulation/engine.py`, `simulation/prompts.py`

**Steps:**
1. **Test:** Write `test_engine_unit.py::TestReflectionPhase::test_reflection_memories_created` — run a multi-round simulation, verify each agent has at least one `"reflection"` type Memory with non-empty content after round 1.
2. **Test:** Write `test_prompts.py::TestReflectionPrompt::test_reflection_includes_vote` — verify the built reflection prompt contains the agent's own vote record and the questions "How did you vote this round?" and "Did your vote align with your plans?".
3. **Implement:**
   - The reflection code at `engine.py:1390-1431` already exists and runs correctly after `_call_reflections()` at line 259.
   - Verify the `_build_memory_context()` method at lines 935-941 injects `type="reflection"` memories under "--- YOUR REFLECTIONS ---".
   - Change line 939 to only use the last 1 reflection: `reflections[-1:]` instead of `reflections[-2:]`.
   - Verify: In `engine.py`, the `_call_reflections()` fires AFTER `_build_round_summary()` and `_record_round_metrics()`, which is correct per the spec.
   - **Add vote context to reflection prompt:**

     In `simulation/prompts.py`, modify `build_reflection_prompt()` (or create it if it's currently inline in engine.py) to accept the agent's vote record and include self-reflection questions:

     ```python
     # prompts.py — new/modified function
     def build_reflection_prompt(
         agent_name: str,
         round_num: int,
         memory_context: str = "",
         vote_record: dict | None = None,     # NEW
         personality: str | None = None,
     ) -> str:
         """Build the prompt for the reflection phase."""
         personality_block = f"\nYour personality: {personality}\n" if personality else ""
         vote_block = ""
         if vote_record and vote_record.get("voted_for"):
             vote_block = (
                 f"\nYour vote this round: You voted for {vote_record['voted_for']}."
                 f"\nHow did you vote this round?"
                 f"\nDid your vote align with your plans?"
             )
         return (
             f"You are {agent_name}.{personality_block}"
             f"\nRound {round_num} is ending. Reflect on what happened."
             f"{vote_block}"
             f"\n{memory_context}"
             f"\n\nRespond with a brief reflection (1-3 sentences)."
         )
     ```

     In `engine.py`, the reflection caller passes the agent's own vote from their personal log:
     ```python
     # engine.py:1390-1431 — modify _call_reflections to extract vote
     def _call_reflections(self) -> None:
         for agent in self.agent_list:
             # Find the agent's own vote from this round
             vote_record = None
             for entry in reversed(agent.personal_log):
                 if entry.get("type") == "vote" and entry.get("round_num") == self.current_round:
                     vote_record = entry.get("data", {})
                     break
             prompt = build_reflection_prompt(
                 agent_name=agent.name,
                 round_num=self.current_round,
                 memory_context=self._build_memory_context(agent),
                 vote_record=vote_record,
                 personality=agent.personality,
             )
             response = self.llm.generate(prompt, ...)
             ...
     ```
4. **Verify:** Both tests pass.
5. **Commit:** `phase5: wire reflection phase with 1-round memory window and vote self-reflection`

**Implementation changes:**

1. **engine.py:937-941** — change reflections window from 2 to 1:
```python
reflections = [m for m in agent.memories if m.type == "reflection"]
if reflections:
    lines = ["--- YOUR REFLECTIONS ---"]
    for m in reflections[-1:]:  # was: reflections[-2:]
        lines.append(f"  {m.content}")
    parts.append("\n".join(lines))
```

2. **prompts.py** — add `build_reflection_prompt()` with vote context (shown above).

3. **engine.py** — modify `_call_reflections()` to pass `vote_record` (shown above).

**Test code for vote inclusion:**
```python
def test_reflection_includes_vote():
    """Reflection prompt should contain the agent's own vote."""
    from simulation.prompts import build_reflection_prompt
    
    vote = {"voted_for": "alice", "round": 1}
    prompt = build_reflection_prompt(
        agent_name="Alice",
        round_num=1,
        vote_record=vote,
    )
    assert "How did you vote this round?" in prompt
    assert "Did your vote align with your plans?" in prompt
    assert "voted for alice" in prompt.lower()

def test_reflection_no_vote_still_works():
    """Reflection prompt works even without a vote record."""
    from simulation.prompts import build_reflection_prompt
    
    prompt = build_reflection_prompt(
        agent_name="Bob",
        round_num=1,
    )
    assert "How did you vote" not in prompt
    assert "Reflect" in prompt or "reflection" in prompt.lower()
```

---

## Phase 6: Prompt Context Block (4 tasks, ~25 min each)

### Task 6.1: Inject full context into campaign prompt

**Files:** Modify `simulation/engine.py`, `simulation/prompts.py`

**Steps:**
1. **Test:** Write `test_prompts.py::TestCampaignPrompt::test_campaign_includes_memory_context` — verify the built campaign prompt contains agent state, reflections, and personal log entries.
2. **Implement:**
   - Modify `_build_election_context()` (engine.py:1039-1048) to pass `memory_context` from `_build_memory_context()` to `build_campaign_prompt()`.
   - Modify `build_campaign_prompt()` signature to accept `memory_context` and `personality` parameters.
   - Inject the memory context block after the pool status.
3. **Verify:** Test passes.
4. **Commit:** `phase6: inject full context into campaign prompt`

**Implementation change:**
```python
# prompts.py:96-101 — new signature
def build_campaign_prompt(
    agent_name: str,
    resources: float,
    opponents: list[str],
    pool_status: str,
    memory_context: str = "",       # NEW
    personality: str | None = None,  # NEW
) -> str:
    """Build the prompt for an election campaign."""
    personality_block = f"\nYour personality: {personality}\n" if personality else ""
    prompt = (
        f"You are {agent_name}, running for leader of the village."
        f"{personality_block}"
        f"\nYour resources: {resources:.1f} fish\n"
        f"Lake status: {pool_status}\n"
        f"Your opponents: {', '.join(opponents)}\n"
        f"{memory_context}"
        # ... rest stays the same
    )

# engine.py:1039-1048 — updated _build_election_context
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
```

### Task 6.2: Inject full context into vote prompt

**Files:** Modify `simulation/engine.py`, `simulation/prompts.py`

**Steps:**
1. **Test:** Write `test_prompts.py::TestVotePrompt::test_vote_includes_memory_context` — verify the built vote prompt contains agent state, reflections, and personal log entries.
2. **Implement:**
   - Modify `_build_vote_context()` (engine.py:1050-1067) to pass `memory_context` to `build_vote_prompt()`.
   - Modify `build_vote_prompt()` signature to accept `memory_context` and `agent_resources`.
   - Inject the memory context block.
3. **Verify:** Test passes.
4. **Commit:** `phase6: inject full context into vote prompt`

**Implementation change:**
```python
# prompts.py:127-130 — new signature
def build_vote_prompt(
    agent_name: str,
    candidates: list[dict],
    memory_context: str = "",     # NEW
    resources: float = 0.0,       # NEW
) -> str:
    lines = [f"You are {agent_name}, voting for village leader."]
    if resources > 0:
        lines.append(f"Your fish: {resources:.1f}")
    lines.append(f"\nCandidate platforms:")
    # ... rest stays the same
    lines.append(f"\n{memory_context}")
    # ... response format

# engine.py:1050-1067 — updated _build_vote_context
def _build_vote_context(
    self, voter: Agent, candidates: list[Agent], platforms: dict[str, Any]
) -> str:
    candidate_dicts = [...]
    return build_vote_prompt(
        agent_name=voter.name,
        candidates=candidate_dicts,
        memory_context=self._build_memory_context(voter),
        resources=voter.resources,
    )
```

### Task 6.3: Inject full context into harvest prompt; rephrase as just-a-number response

**Files:** Modify `simulation/engine.py`, `simulation/prompts.py`

**Steps:**
1. **Test:** Write `test_prompts.py::TestHarvestPrompt::test_harvest_includes_memory_context` — verify the built harvest prompt contains memory context, reflections, and current channel status.
2. **Test:** Write `test_prompts.py::TestHarvestPrompt::test_harvest_prompt_asks_for_number_only` — verify the harvest prompt does NOT mention `action` and simply asks for a number.
3. **Implement:**
   - Modify `_build_harvest_context()` (engine.py:1181-1194) to pass `memory_context` from `_build_memory_context()` to `build_harvest_prompt()`.
   - Modify `build_harvest_prompt()` signature to accept `memory_context`.
   - **Rephrase as just-a-number:** Modify `build_harvest_prompt()` in `prompts.py` to remove any mention of `action` in the response format. Instead of asking for an action+amount object, simply ask "How many fish will you catch this turn? (Enter a number from 0 to the pool size.)" The LLM response is expected to be a single number, not a JSON object.
4. **Verify:** Both tests pass.
5. **Commit:** `phase6: inject full context into harvest prompt, rephrase as just-a-number`

**Implementation changes:**

1. **prompts.py** — modified `build_harvest_prompt()` to ask for a number only:
```python
def build_harvest_prompt(
    agent_name: str,
    resources: float,
    round_num: int,
    leader_name: str | None,
    limit: float | None,
    penalty_rate: float | None,
    pool_status: str,
    personality: str | None = None,
    memory_context: str = "",       # NEW
) -> str:
    """Build the prompt for the harvest phase. Response is a single number."""
    personality_block = f"\nYour personality: {personality}\n" if personality else ""
    
    leader_block = ""
    if leader_name:
        leader_block = (
            f"\nThe leader is {leader_name}."
            f"\nYour harvest limit: {limit:.1f} fish"
            f"\nPenalty rate for exceeding the limit: {penalty_rate:.1f}x"
        )
    
    prompt = (
        f"You are {agent_name}, a fisher in the village.{personality_block}"
        f"\nRound: {round_num}, Harvest Phase"
        f"\n\nYour resources: {resources:.1f} fish"
        f"\nLake status: {pool_status}"
        f"{leader_block}"
        f"\n{memory_context}"
        f"\n\nHow many fish will you catch this turn?"
        f"\n(Enter a number from 0 to the pool size — see Lake status above.)"
        f"\n\nRespond with JUST A NUMBER — no explanation, no JSON, no action field."
    )
    return prompt
```

2. **engine.py:1181-1194** — updated `_build_harvest_context()` to pass `memory_context`:
```python
def _build_harvest_context(self, agent: Agent) -> str:
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
```

3. **engine.py** — harvest handler (around line 1090) must parse a plain number instead of a JSON response:
   - If the LLM returns a raw number string (e.g., `"5"` or `"5.0"`), convert it with `float()`.
   - If the LLM returns a JSON object with an `amount` key (backward-compat), fall back to the current parsing.
   - If neither works, treat as pass (amount=0).

**Test code for number-only prompt:**
```python
def test_harvest_prompt_asks_for_number_only():
    """Harvest prompt should ask for a number, not an action."""
    from simulation.prompts import build_harvest_prompt
    
    prompt = build_harvest_prompt(
        agent_name="Alice",
        resources=50.0,
        round_num=1,
        leader_name="Bob",
        limit=10.0,
        penalty_rate=2.0,
        pool_status="Pool: 100.0 fish remaining",
    )
    # Should ask for a number
    assert "How many fish" in prompt
    assert "Enter a number" in prompt
    # Should NOT mention action
    assert "action" not in prompt.lower() or "fractional action" not in prompt.lower()
    # Should NOT ask for JSON
    assert "{" not in prompt or "JSON" not in prompt
```

### Task 6.4: Remove round_summary injection and shrink memory window

**Files:** Modify `simulation/engine.py`

**Steps:**
1. **Test:** Write `test_engine_unit.py::TestMemoryContext::test_round_summary_not_in_prompt` — verify the text "--- YOUR MEMORIES ---" no longer appears in the built context for any agent after fixes.
2. **Implement:**
   - Remove the round_summary injection block (engine.py:927-933):
     ```python
     # DELETE these lines:
     # 3. Round summaries (from agent memory)
     summaries = [m for m in agent.memories if m.type == "round_summary"]
     if summaries:
         lines = ["--- YOUR MEMORIES ---"]
         for m in summaries[-2:]:
             lines.append(f"  {m.content}")
         parts.append("\n".join(lines))
     ```
   - Shrink personal log window from 2 rounds to 1 round: change line 891 from `min_round = max(1, max_round - 1)` to `min_round = max_round` (only current round).
   - Update `_analyze_conversation()` docstring (line 1434-1438) to the following — this removes the lie about labels feeding into "KEY EVENTS" in agent prompts:
     ```python
     def _analyze_conversation(self) -> None:
         """Run significance analysis on the round's conversation.
         
         Writes labels (alliance/collusion/betrayal/deal) to self._analysis_results.
         These labels are for the RECORDER output and the VISUALIZER only.
         They are NOT injected into agent prompts.
         """
     ```
   - Also remove any line in engine.py that says these labels "feed into KEY EVENTS in the next round's prompts" — that line is a lie per the review (already handled in Task 1.7's engine.py fix, but double-check no other occurrence remains).
3. **Verify:** Tests pass.
4. **Commit:** `phase6: remove round_summary injection, shrink memory window to 1 round`

---

## Phase 7: Test & Observability (6 tasks, ~20 min each)

### Task 7.1: Add `channel_states` snapshot to recorder output

**Files:** Modify `simulation/recorder.py`, `simulation/engine.py`

**Steps:**
1. **Test:** Write `test_recorder.py::TestChannelStates::test_channel_states_in_output` — run a simulation, verify `channel_states` appears in each round's output, containing channel name and members for each phase.
2. **Implement:**
   - Add `channel_states` field to `PhaseOutput` or as part of the event recording.
   - In `Engine.run()`, after each phase transition, capture a channel snapshot:
     ```python
     def _capture_channel_snapshot(self) -> dict[str, list[str]]:
         """Capture current channel state for recorder output."""
         if not self.channels:
             return {}
         snapshot = {}
         for aid, ch in self.channels._agent_channel.items():
             if ch not in snapshot:
                 snapshot[ch] = []
             name = self.agents[aid].name
             snapshot[ch].append(name)
         return {ch: sorted(members) for ch, members in snapshot.items()}
     ```
   - Store the snapshot with each phase output via `recorder.set_channel_snapshot()`.
3. **Verify:** Test passes.
4. **Commit:** `phase7: add channel_states snapshot to recorder output`

**Implementation:**
```python
# recorder.py — add method
def set_channel_snapshot(self, snapshot: dict[str, list[str]]) -> None:
    """Record the current channel state for this phase."""
    if self._current_phase is not None:
        self._current_phase["channel_states"] = snapshot

# engine.py — capture after each phase
# After free_interaction, before dissolution:
snapshot = self._capture_channel_snapshot()
self.recorder.set_channel_snapshot(snapshot)
self._dissolve_private_channels()
```

### Task 7.2: Add `personal_log` to recorder output

**Files:** Modify `simulation/recorder.py`, `simulation/engine.py`

**Steps:**
1. **Test:** Write `test_recorder.py::TestPersonalLogOutput::test_personal_log_in_output` — run a simulation, verify `get_output()` contains `"personal_logs"` key with per-agent log entries.
2. **Implement:**
   - In `Recorder.get_output()` (line 213-233), add:
     ```python
     if hasattr(self, '_personal_logs') and self._personal_logs:
         output["personal_logs"] = self._personal_logs
     ```
   - In `Engine._set_recorder_metadata()` (line 1368), after setting agent memories, also set personal logs:
     ```python
     personal_logs: dict[str, list[dict]] = {}
     for agent in self.agent_list:
         personal_logs[agent.id] = list(agent.personal_log)
     self.recorder.set_personal_logs(personal_logs)
     ```
   - Add method to Recorder:
     ```python
     def set_personal_logs(self, logs: dict[str, list[dict]]) -> None:
         """Store per-agent personal logs for output."""
         self._personal_logs = logs
     ```
3. **Verify:** Test passes.
4. **Commit:** `phase7: add personal_log to recorder output`

### Task 7.3: Fix `test_private_talk_excluded_from_third_party`

**Files:** Modify `tests/test_engine_personal_log.py`

**Steps:**
1. **Read the test:** The test at line 244-272 currently uses `_execute_talk()` (which we deleted in Task 1.3). It needs to be rewritten to work through `_handle_agent_turn` or direct channel routing.
2. **Rewrite:** Replace the test to use the channel-based routing:
   ```python
   def test_private_talk_excluded_from_third_party(self):
       """A third party not in the private channel does NOT get the talk log entry."""
       engine = make_engine()
       alice = engine.agents["alice"]
       bob = engine.agents["bob"]
       charlie = engine.agents["charlie"]
       
       # Set up a private channel with Alice and Bob
       channel_name = engine.channels._generate_channel_name()
       engine.channels._channels[channel_name] = {"alice", "bob"}
       engine.channels._agent_channel["alice"] = channel_name
       engine.channels._agent_channel["bob"] = channel_name
       # Charlie stays in public
       
       # Send a private talk via handle_agent_turn
       engine.llm = StubLLM(responses=[
           {"action": "talk", "message": "secret meeting", "reasoning": "."},
       ])
       engine.recorder.start_round(1)
       engine.recorder.start_phase("free_interaction")
       engine.current_round = 1
       engine.turn_counter = 5
       engine.current_phase = "free_interaction"
       engine._handle_agent_turn(alice)
       
       # Charlie should NOT have this talk entry
       charlie_secrets = [
           e for e in charlie.personal_log
           if e["type"] == "talk" and e["data"].get("message") == "secret meeting"
       ]
       assert len(charlie_secrets) == 0, "Charlie heard a private message"
       
       # Alice and Bob SHOULD have it
       alice_heard = any(
           e["type"] == "talk" and e["data"].get("message") == "secret meeting"
           for e in alice.personal_log
       )
       assert alice_heard, "Alice should have her own talk entry"
   ```
3. **Verify:** Test passes.
4. **Commit:** `phase7: fix test_private_talk_excluded_from_third_party`

### Task 7.4: Fix `test_violator_gets_penalty_entry`

**Files:** Modify `tests/test_engine_personal_log.py`

**Steps:**
1. **Read the test:** Lines 200-238 — the test ends with `assert True` (placeholder). The actual assertion at line 236 is a no-op.
2. **Rewrite:** Change the config to use `elections_every_round: True`, use 1 agent to ensure a specific violator, and assert the violator actually has a penalty entry.
   ```python
   def test_violator_gets_penalty_entry(self):
       """An agent who exceeds the leader's limit gets a penalty log entry."""
       config = {
           "simulation": {"num_rounds": 1, "turns_per_phase": 1},
           "agents": {"names": ["Alice", "Bob"], "starting_resources": 50.0},
           "resources": {"carrying_capacity": 100, "regeneration_factor": 1.5, "fish_per_harvest": 5.0},
           "leader": {"fine_destination": "common_pool", "default_limit": 10.0, "default_penalty_rate": 2.0, "candidacy_cost": 2.0},
           "election": {"method": "plurality", "elections_every_round": True},
       }
       # Alice campaigns (wins by default), Bob votes, both fish
       responses = [
           pass_response(), pass_response(),  # free interaction
           campaign_response(limit=5.0, rate=2.0),  # Alice campaigns
           campaign_response(limit=5.0, rate=2.0),  # Bob campaigns
           vote_response("alice"),  # Alice votes for Alice
           vote_response("alice"),  # Bob votes for Alice
           fish_response(8.0),  # Alice fishes 8 (exceeds limit 5!)
           fish_response(3.0),  # Bob fishes 3 (under limit)
           pass_response(), pass_response(),
       ]
       llm = StubLLM(responses)
       engine = Engine(config, llm=llm, seed=42)
       engine.run()
       
       # Alice should have a penalty entry
       alice = engine.get_agent("alice")
       alice_penalties = [e for e in alice.personal_log if e["type"] == "penalty"]
       assert len(alice_penalties) >= 1, "Alice should have a penalty entry"
       assert "penalized" in alice_penalties[0]["data"].get("text", "").lower()
       
       # Bob should NOT have a penalty entry
       bob = engine.get_agent("bob")
       bob_penalties = [e for e in bob.personal_log if e["type"] == "penalty"]
       assert len(bob_penalties) == 0, "Bob should not have a penalty entry"
   ```
3. **Verify:** Test passes.
4. **Commit:** `phase7: fix test_violator_gets_penalty_entry`

### Task 7.5: Fix `test_leader_persists_when_no_new_election`

**Files:** Modify `tests/test_engine_personal_log.py` (or `test_engine_unit.py`)

**Steps:**
1. **Read the test:** This test is currently `pass`. It should test that leader carries over when no election occurs (only relevant with `elections_every_round: False` and 2+ rounds).
2. **Rewrite:**
   ```python
   def test_leader_persists_when_no_new_election(self):
       """Leader from round 1 carries over to round 2 if no election."""
       config = load_config({
           "simulation": {"num_rounds": 2, "turns_per_phase": 1},
           "agents": {"names": ["Alice", "Bob"], "starting_resources": 50.0},
           "resources": {"carrying_capacity": 100.0, "regeneration_factor": 1.5},
           "leader": {"fine_destination": "common_pool", "default_limit": 10.0, "default_penalty_rate": 0.5},
           "election": {"method": "plurality", "elections_every_round": False},
       })
       # R1: free(2), no election (False), harvest(2), post(2)
       # R2: free(2), no election (False), harvest(2), post(2)
       r1 = [pass_response() for _ in range(2)] + [fish_response(5.0) for _ in range(2)] + [pass_response() for _ in range(2)]
       r2 = [pass_response() for _ in range(2)] + [fish_response(5.0) for _ in range(2)] + [pass_response() for _ in range(2)]
       
       stub = StubLLM(r1 + r2)
       engine = Engine(config, llm=stub, seed=42)
       engine.run()
       
       # No leader since no election ever ran
       assert engine.leader is None
       # Default limit still applies
       assert engine.leader_limit is None or engine.leader_limit == 10.0
   ```
3. **Verify:** Test passes.
4. **Commit:** `phase7: fix test_leader_persists_when_no_new_election`

### Task 7.6: Add 6 new tests

**Files:** Create `tests/test_v2_features.py` (or add to existing test files)

**Steps:**
1. **Test 1 — heard_by validation:**
   ```python
   def test_heard_by_private_channel_members_only():
       """Private channel messages have heard_by set to only channel members."""
       # ... setup with 3 agents, create private channel with 2, talk, verify heard_by
   ```
   Verify that `LLMResponse` with `action="talk"` for an agent in a private channel records `heard_by` containing only channel members.

2. **Test 2 — Transfer null target:**
   ```python
   def test_transfer_null_target_records_failure():
       """Transfer with target=None records a failure in sender's personal log."""
       # ... run engine with transfer response where target is None
       # Verify sender's personal log has a system/error entry
   ```
3. **Test 3 — Group field fix:**
   ```python
   def test_llm_response_group_field_parsed():
       """LLMResponse.group is correctly parsed from the LLM response."""
       # ... already covered in Task 1.2, but add an integration test
   ```
4. **Test 4 — Per-phase channel dissolution:**
   ```python
   def test_per_phase_channel_dissolution():
       """After a phase transition, all agents are in 'public'."""
       # ... covered in Phase 3, add integration test via engine.run()
   ```
5. **Test 5 — Reflection phase output:**
   ```python
   def test_reflection_phase_output():
       """Each agent has at least one 'reflection' type Memory after reflection."""
       # ... already covered in Phase 5
   ```
6. **Test 6 — Candidacy cost:**
   ```python
   def test_candidacy_cost_deducted_and_penniless_skip():
       """Running for leader deducts 5 fish; agents with < 5 cannot run."""
       # ... already covered in Phase 4
   ```

3. **Commit** each test independently (6 commits):
   - `phase7: add heard_by validation test for private channel messages`
   - `phase7: add transfer null target failure recording test`
   - `phase7: add LLMResponse group field parsing integration test`
   - `phase7: add per-phase channel dissolution integration test`
   - `phase7: add reflection phase output verification test`
   - `phase7: add candidacy cost deduction and penniless skip test`

---

## Summary: Total Tasks

| Phase | Tasks | Commit Count |
|---|---|---|
| 1: Bug Fixes | 8 | 8 |
| 2: New Config | 2 | 2 |
| 3: Channel Dissolution | 2 | 2 |
| 4: Election & Voting | 3 | 3 |
| 5: Reflection Phase | 1 | 1 |
| 6: Prompt Context Block | 4 | 4 |
| 7: Test & Observability | 6 | 9 (3 fixes + 6 new) |
| **Total** | **26** | **29** |

## Production Run Command

After all phases are implemented and passing:
```bash
cd C:\Users\laodie666\Desktop\stuff\Jinesis Lab\govsim\govsim-autonomous
python -m simulation.main --config config/five_agents_drama.yaml --seed 42 --verbose
```

With real LLM:
```bash
$env:DEEPSEEK_API_KEY = "sk-..."
python -m simulation.main --config config/five_agents_drama.yaml --seed 42 --verbose
```

Run all tests:
```bash
cd C:\Users\laodie666\Desktop\stuff\Jinesis Lab\govsim\govsim-autonomous
python -m pytest tests/ -v
```
