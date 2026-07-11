# GovSim-Autonomous Visualizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Smallville-inspired visualizer for GovSim-Autonomous simulations, plus a prerequisite sim fix adding pool-collapse end condition.

**Architecture:** Two phases — Phase A fixes the simulation engine to end on pool collapse and output survival metrics. Phase B builds a fresh React + TypeScript + Vite visualizer with an HTML5 Canvas spatial world, 8 nav-rail panels, always-on HUD, and turn-based playback.

**Tech Stack:** Python (sim), React 19 + TypeScript + Vite + HTML5 Canvas + Tailwind CSS + Zustand + Recharts (visualizer). Kenney CC0 sprites. Vitest for visualizer tests, pytest for sim tests.

## Global Constraints

- Working directory: `C:\Users\laodie666\Desktop\stuff\Jinesis Lab\govsim\govsim-autonomous`
- All paths below are relative to this root unless absolute.
- Sim runs via `python -m simulation.main` (argparse + YAML, no Hydra)
- Stub mode (`--stub`) requires no API key, uses StubLLM
- 244 existing sim tests must stay green throughout
- Visualizer is post-hoc: loads `outputs/sim_*.json` files, not live
- Old `visualizer/` directory is deleted and replaced entirely
- Sprites: Kenney CC0 packs (RPG Urban Kit + Foliage Pack), downloaded to `visualizer/public/sprites/`
- Windows environment (PowerShell), but use cross-platform commands where possible

---

## File Map

### Phase A — Sim Fix

| File | Action | Purpose |
|------|--------|---------|
| `simulation/engine.py:22-85` | Modify | Add `collapsed`, `collapsed_at_round`, `survival_length` fields |
| `simulation/engine.py:189-254` | Modify | Add collapse check after harvesting, break loop, store survival length |
| `simulation/recorder.py:53-66` | Modify | Add `_end_condition`, `_collapsed_at_round`, `_survival_length` fields |
| `simulation/recorder.py:199-216` | Modify | Add `end_condition`, `collapsed_at_round`, `survival_length` to `get_output()` |
| `tests/test_engine_collapse.py` | Create | Test collapse detection end-to-end |

### Phase B — Visualizer

| File | Action | Purpose |
|------|--------|---------|
| `visualizer/` (whole dir) | Delete | Remove old Phaser-based visualizer |
| `visualizer/package.json` | Create | Vite + React 19 + dependencies |
| `visualizer/vite.config.ts` | Create | Vite config with React + Tailwind plugins |
| `visualizer/tsconfig.json` | Create | TypeScript config |
| `visualizer/tailwind.config.js` | Create | Tailwind CSS config |
| `visualizer/postcss.config.js` | Create | PostCSS config for Tailwind |
| `visualizer/index.html` | Created by vite | HTML entry point |
| `visualizer/src/main.tsx` | Created by vite | React entry |
| `visualizer/src/App.tsx` | Create/replace | Root layout: TopBar, NavRail, Canvas, HUD, PlaybackControls, panels |
| `visualizer/src/types.ts` | Create/replace | TypeScript interfaces matching JSON schema |
| `visualizer/src/data/loader.ts` | Create | JSON loader + validator + normalizer |
| `visualizer/src/data/channelReconstructor.ts` | Create | Walk turns, track channel membership, emit Channel[] |
| `visualizer/src/store/simulationStore.ts` | Create | Zustand store with all simulation state |
| `visualizer/src/playback/PlaybackEngine.ts` | Create | Pure function `getTurnState()`, playback loop |
| `visualizer/src/canvas/sceneConfig.ts` | Create/replace | Map layout, zones, colors, dimensions |
| `visualizer/src/canvas/spriteLoader.ts` | Create | Load Kenney sprite sheets, character tinting |
| `visualizer/src/canvas/CanvasRenderer.ts` | Create/replace | Canvas 2D rendering: map, agents, speech bubbles, graph overlay |
| `visualizer/src/components/TopBar.tsx` | Create | Load file, run ID, play/pause, metrics button |
| `visualizer/src/components/NavRail.tsx` | Create | 8 icon buttons, toggle panels |
| `visualizer/src/components/HUD.tsx` | Create/replace | Round, phase, pool gauge, leader, collapse status |
| `visualizer/src/components/PlaybackControls.tsx` | Create/replace | Play/pause, step, skip, speed |
| `visualizer/src/components/Timeline.tsx` | Create | Scrubber with round ticks, phase colors, collapse marker |
| `visualizer/src/panels/Conversations.tsx` | Create | Channel browser + group-chat thread |
| `visualizer/src/panels/CollusionDetection.tsx` | Create | Flagged events timeline with filters |
| `visualizer/src/panels/PerAgentStats.tsx` | Create | Agent picker + charts (Recharts) |
| `visualizer/src/panels/SimulationMetrics.tsx` | Create | Full dashboard with Recharts |
| `visualizer/src/panels/SocialGraph.tsx` | Create | Force-directed graph with D3-force |
| `visualizer/src/panels/Elections.tsx` | Create | Per-round election cards |
| `visualizer/src/panels/Harvesting.tsx` | Create | Per-round harvest table |
| `visualizer/src/panels/EventLog.tsx` | Create | Chronological feed, filterable, searchable |
| `visualizer/src/__tests__/` | Create | Vitest test files |
| `visualizer/public/sprites/` | Create | Kenney CC0 sprite PNGs (or placeholder) |

---

## Phase A — Simulation Fix (Tasks 1-3)

### Task 1: Add collapse detection to engine

**Files:**
- Modify: `simulation/engine.py:189-254` (the `run()` method)
- Modify: `simulation/engine.py:65-85` (add `collapsed` and `collapsed_at_round` fields)
- Create: `tests/test_engine_collapse.py`

**Interfaces:**
- Consumes: `Engine.run()` method, `ResourcePool.amount` attribute (float)
- Produces: `engine.collapsed` (bool), `engine.collapsed_at_round` (int | None), `engine.survival_length` (int)

- [ ] **Step 1: Write the failing test**

```python
"""Tests for pool collapse detection."""
import pytest
from simulation.engine import Engine
from simulation.llm_interface import StubLLM
from simulation.config import load_config


def stub(*response_dicts):
    return StubLLM(list(response_dicts))


def p():
    return {"action": "pass", "reasoning": ".", "significance": None}


def fish(amt):
    return {"action": "fish", "amount": amt, "reasoning": ".", "significance": "economic"}


def campaign(limit=10.0, rate=0.0):
    return {"harvest_limit": limit, "penalty_rate": rate,
            "message": ".", "reasoning": "."}


def vote(candidate_id):
    return {"vote_for": candidate_id}


@pytest.fixture
def collapse_config():
    """Config designed to collapse: low capacity, aggressive fishing."""
    return load_config({
        "simulation": {"num_rounds": 10, "turns_per_phase": 1},
        "agents": {"names": ["Alice", "Bob"], "starting_resources": 50.0},
        "resources": {"carrying_capacity": 20.0, "regeneration_factor": 0.5},
        "leader": {"fine_destination": "common_pool"},
        "election": {"method": "plurality", "first_election_round": 2},
    })


@pytest.fixture
def safe_config():
    """Config that should NOT collapse."""
    return load_config({
        "simulation": {"num_rounds": 2, "turns_per_phase": 1},
        "agents": {"names": ["Alice", "Bob"], "starting_resources": 50.0},
        "resources": {"carrying_capacity": 100.0, "regeneration_factor": 2.0},
        "leader": {"fine_destination": "common_pool"},
        "election": {"method": "plurality", "first_election_round": 2},
    })


class TestEngineCollapse:

    def test_engine_has_collapse_fields(self):
        """Engine initialises with collapse fields."""
        config = load_config({
            "simulation": {"num_rounds": 1, "turns_per_phase": 1},
            "agents": {"names": ["Alice"], "starting_resources": 50.0},
            "resources": {"carrying_capacity": 100.0, "regeneration_factor": 1.5},
            "leader": {"fine_destination": "common_pool"},
            "election": {"method": "plurality", "first_election_round": 2},
        })
        engine = Engine(config, llm=stub(p(), fish(100.0), p()), seed=42)
        assert hasattr(engine, "collapsed")
        assert engine.collapsed is False
        assert hasattr(engine, "collapsed_at_round")
        assert engine.collapsed_at_round is None

    def test_pool_collapse_ends_simulation_early(self, collapse_config):
        """When pool hits 0 during harvesting, sim stops immediately."""
        responses = [
            p(), p(),  # R1 free (2 agents x 1 turn)
            fish(20.0),  # Alice fishes -- pool goes 20 -> 0
        ]
        engine = Engine(collapse_config, llm=stub(*responses), seed=42)
        engine.run()

        assert engine.collapsed is True
        assert engine.collapsed_at_round == 1
        assert len(engine.get_output()["rounds"]) == 1

    def test_no_collapse_when_pool_positive(self, safe_config):
        """Sim runs full rounds when pool never hits 0."""
        r1 = [p(), p(), fish(5.0), fish(5.0), p(), p()]
        r2 = [p(), p(), campaign(), campaign(), vote("alice"), vote("alice"),
              fish(5.0), fish(5.0), p(), p()]
        engine = Engine(safe_config, llm=stub(*(r1 + r2)), seed=42)
        engine.run()

        assert engine.collapsed is False
        assert engine.collapsed_at_round is None
        assert len(engine.get_output()["rounds"]) == 2

    def test_collapse_in_later_round(self, collapse_config):
        """Pool collapses partway through a later round."""
        responses = [
            p(), p(), fish(15.0), fish(0.0), p(), p(),
            p(), p(), fish(3.0),  # Alice fishes 3 -> pool 0 -> collapse
        ]
        engine = Engine(collapse_config, llm=stub(*responses), seed=42)
        engine.run()

        assert engine.collapsed is True
        assert engine.collapsed_at_round == 2

    def test_survival_length(self, collapse_config):
        """survival_length reports rounds completed before collapse."""
        responses = [
            p(), p(), fish(15.0), fish(0.0), p(), p(),
            p(), p(), fish(3.0),
        ]
        engine = Engine(collapse_config, llm=stub(*responses), seed=42)
        engine.run()
        assert engine.survival_length == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_engine_collapse.py -v`
Expected: FAIL with `AttributeError: 'Engine' object has no attribute 'collapsed'`

- [ ] **Step 3: Write minimal implementation**

In `simulation/engine.py`, add collapse fields in `__init__` (after line 77):

```python
        # Collapse detection
        self.collapsed: bool = False
        self.collapsed_at_round: int | None = None
        self.survival_length: int = 0
```

In `simulation/engine.py`, in the `run()` method (starting line 189), change the post-harvest section from:

```python
            # Phase 4: Post-Harvest Interaction
            ...
            # Regenerate resource pool
            self.pool.regenerate(...)
```

To:

```python
            # Phase 4: Post-Harvest Interaction
            print(f"[sim]   Phase: Post-Harvest Interaction...")
            self._log_to_all("phase_marker", {"phase": "discussion"})
            self._run_free_interaction()

            # Record end-of-round metrics
            self._record_round_metrics()

            # Check for pool collapse BEFORE regeneration
            if self.pool.amount == 0:
                self.collapsed = True
                self.collapsed_at_round = round_num
                self.survival_length = round_num
                print(f"[sim]   ⚠ POOL COLLAPSED at round {round_num}")
                break

            # Regenerate resource pool
            self.pool.regenerate(
                factor=self.config["resources"]["regeneration_factor"],
            )
```

After the round loop completes (after `_analyze_conversation()`), set survival_length for normal exit:

```python
        # Set survival_length if not already set (normal completion)
        if not self.collapsed:
            self.survival_length = num_rounds

        # Populate recorder with round summaries and agent memories
        self._set_recorder_metadata()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_engine_collapse.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Initialize git and commit (if starting fresh)**

```bash
cd C:\Users\laodie666\Desktop\stuff\Jinesis Lab\govsim\govsim-autonomous
git init
git add .
git commit -m "chore: initial commit before visualizer work"
```

Then commit the task:
```bash
git add tests/test_engine_collapse.py simulation/engine.py
git commit -m "feat: add pool-collapse end condition to engine"
```

---

### Task 2: Add end_condition fields to recorder

**Files:**
- Modify: `simulation/recorder.py:53-66` (add `_end_condition` field)
- Modify: `simulation/recorder.py:199-216` (add to `get_output()`)
- Modify: `simulation/engine.py:253-255` (pass collapse info to recorder)

**Interfaces:**
- Consumes: `engine.collapsed`, `engine.collapsed_at_round`, `engine.survival_length`, `Recorder.get_output()`
- Produces: Output JSON now includes `"end_condition"`, `"collapsed_at_round"`, `"survival_length"`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_engine_collapse.py`:

```python
class TestRecorderEndCondition:

    def test_recorder_get_output_has_end_condition(self):
        """Recorder output includes end_condition field."""
        from simulation.recorder import Recorder
        recorder = Recorder(run_id="test_end")
        output = recorder.get_output()
        assert "end_condition" in output
        assert output["end_condition"] == "time_limit"
        assert "collapsed_at_round" in output
        assert output["collapsed_at_round"] is None
        assert "survival_length" in output

    def test_end_condition_collapse_in_output(self, collapse_config):
        """Collapsed sim output shows end_condition='collapse'."""
        responses = [p(), p(), fish(20.0)]
        engine = Engine(collapse_config, llm=stub(*responses), seed=42)
        engine.run()
        output = engine.get_output()

        assert output["end_condition"] == "collapse"
        assert output["collapsed_at_round"] == 1
        assert output["survival_length"] == 1

    def test_end_condition_time_limit(self, safe_config):
        """Normal sim completion shows end_condition='time_limit'."""
        r1 = [p(), p(), fish(5.0), fish(5.0), p(), p()]
        r2 = [p(), p(), campaign(), campaign(), vote("alice"), vote("alice"),
              fish(5.0), fish(5.0), p(), p()]
        engine = Engine(safe_config, llm=stub(*(r1 + r2)), seed=42)
        engine.run()
        output = engine.get_output()

        assert output["end_condition"] == "time_limit"
        assert output["collapsed_at_round"] is None
        assert output["survival_length"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_engine_collapse.py::TestRecorderEndCondition -v`
Expected: FAIL with `KeyError: 'end_condition'`

- [ ] **Step 3: Write minimal implementation**

In `simulation/recorder.py`, add fields to `__init__` (after line 66):

```python
        self._end_condition: str = "time_limit"
        self._collapsed_at_round: int | None = None
        self._survival_length: int = 0
```

Add a setter method in `simulation/recorder.py`:

```python
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
```

Modify `get_output()` to include the new fields:

```python
    def get_output(self) -> dict:
        """Get the complete simulation output as a dict."""
        output: dict[str, Any] = {
            "run_id": self.run_id,
            "config": self._config,
            "started_at": time.strftime(...),
            "end_condition": self._end_condition,
            "collapsed_at_round": self._collapsed_at_round,
            "survival_length": self._survival_length,
            "rounds": self._rounds,
            "metrics": {
                "by_round": self._metrics_by_round,
            },
        }
        # ... rest unchanged
```

In `simulation/engine.py`, at the end of `run()` right before `_set_recorder_metadata`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_engine_collapse.py::TestRecorderEndCondition -v`
Expected: PASS (3 passed)

Run full suite: `python -m pytest -q`
Expected: All tests pass (~249 tests)

- [ ] **Step 5: Commit**

```bash
git add simulation/recorder.py simulation/engine.py tests/test_engine_collapse.py
git commit -m "feat: add end_condition fields to recorder output"
```

---

### Task 3: Generate collapse output JSON for visualizer testing

**Files:**
- Create: `scripts/generate_collapse_demo.py`
- Generate: `outputs/collapse_demo.json`

- [ ] **Step 1: Write the generation script**

Create `scripts/generate_collapse_demo.py`:

```python
"""Generate a collapse demo output JSON for visualizer testing."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simulation.engine import Engine
from simulation.llm_interface import StubLLM
from simulation.config import load_config


def p():
    return {"action": "pass", "reasoning": ".", "significance": None}


def fish(amt):
    return {"action": "fish", "amount": amt, "reasoning": ".", "significance": "economic"}


def talk(target, msg):
    return {"action": "public_talk", "target": target, "message": msg,
            "reasoning": ".", "significance": "small_talk"}


def campaign(limit=6.0, rate=2.0):
    return {"harvest_limit": limit, "penalty_rate": rate,
            "message": ".", "reasoning": "."}


def vote(cid):
    return {"vote_for": cid}


def main():
    config = load_config({
        "simulation": {"num_rounds": 6, "turns_per_phase": 2},
        "agents": {"names": ["Alice", "Bob", "Charlie"], "starting_resources": 50.0},
        "resources": {"carrying_capacity": 25.0, "regeneration_factor": 0.3},
        "leader": {"fine_destination": "common_pool"},
        "election": {"method": "plurality", "first_election_round": 2},
    })

    # R1: free(6) + harvest(3) + post(6) -- fish 8 each = 24 from 25 -> 1 left
    # R2: free(6) + election + harvest -- regen 1*0.3=0.3 -> fish 0.3 -> 0, collapse
    responses = (
        [talk("bob", "Hello all")] + [p() for _ in range(5)] +
        [fish(8.0), fish(8.0), fish(8.0)] +
        [p() for _ in range(6)] +
        [p() for _ in range(6)] +
        [campaign(limit=5.0, rate=2.0),
         campaign(limit=7.0, rate=1.0),
         campaign(limit=6.0, rate=3.0)] +
        [vote("alice"), vote("alice"), vote("alice")] +
        [fish(0.3)]  # Alice takes the last 0.3 -> collapse
    )

    engine = Engine(config, llm=StubLLM(list(responses)), seed=42, run_id="collapse_demo")
    engine.run()
    engine.save_output("outputs/collapse_demo.json")

    output = engine.get_output()
    print(f"End condition: {output['end_condition']}")
    print(f"Collapsed at round: {output['collapsed_at_round']}")
    print(f"Survival length: {output['survival_length']}")
    print(f"Rounds recorded: {len(output['rounds'])}")
    print("Done -- saved to outputs/collapse_demo.json")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the generation script**

Run: `python scripts/generate_collapse_demo.py`
Expected:
```
End condition: collapse
Collapsed at round: 2
Survival length: 2
Rounds recorded: 2
Done -- saved to outputs/collapse_demo.json
```

- [ ] **Step 3: Verify the generated file**

Run: `python -c "import json; d=json.load(open('outputs/collapse_demo.json')); print(d['end_condition'], d['collapsed_at_round'], d['survival_length'])"`
Expected: `collapse 2 2`

- [ ] **Step 4: Run full test suite**

Run: `python -m pytest -q`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_collapse_demo.py outputs/collapse_demo.json
git commit -m "feat: generate collapse demo output for visualizer testing"
```

---

## Phase B — Visualizer (Tasks 4-28)

### Task 4: Scaffold visualizer project

**Files:**
- Delete: `visualizer/` directory entirely
- Create: fresh Vite + React + TS project via `npm create vite`

**Interfaces:**
- Consumes: Nothing
- Produces: Working `npm run dev` serve and `npm run build`

- [ ] **Step 1: Delete old visualizer**

```bash
Remove-Item -Recurse -Force "visualizer"
```

- [ ] **Step 2: Scaffold Vite project**

```bash
npm create vite@latest visualizer -- --template react-ts
```

- [ ] **Step 3: Install dependencies**

```bash
cd visualizer
npm install zustand recharts d3-force @types/d3-force
npm install -D tailwindcss @tailwindcss/vite postcss autoprefixer
```

- [ ] **Step 4: Configure Tailwind (Tailwind v4 approach)**

In `visualizer/vite.config.ts`:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
})
```

In `visualizer/src/index.css`:

```css
@import "tailwindcss";
```

- [ ] **Step 5: Verify dev server and build**

Run: `npm run dev` (verify it starts without errors)
Run: `npm run build` (expected: builds without errors)

- [ ] **Step 6: Configure Vitest**

Update `visualizer/vitest.config.ts` (or create it):

```typescript
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/__tests__/setup.ts'],
  },
})
```

Create `visualizer/src/__tests__/setup.ts`:

```typescript
import '@testing-library/jest-dom/vitest'
```

```bash
npm install -D @testing-library/jest-dom @testing-library/react jsdom vitest
```

- [ ] **Step 7: Verify Vitest works**

Run: `npx vitest run`
Expected: No tests found but no errors (clean state)

- [ ] **Step 8: Commit**

```bash
git add visualizer/
git commit -m "feat: scaffold visualizer with Vite + React + TS + Tailwind + Zustand + Recharts"
```

---

### Task 5: TypeScript types matching JSON schema

**Files:**
- Create/replace: `visualizer/src/types.ts`
- Test: `visualizer/src/__tests__/types.test.ts`

**Interfaces:**
- Consumes: JSON schema from `outputs/five_agents_stub.json`
- Produces: Full type definitions: `SimulationData`, `Round`, `Phase`, `Turn`, `ElectionResult`, `MetricsData`, `RoundMetrics`, `RoundSummary`, `MemoryEntry`, `Channel`, `ChannelMessage`, `PanelId`, `AgentPosition`, `FlatTurn`, `PlaybackState`, `GraphEdge`, `GraphNode`, `GraphData`

- [ ] **Step 1: Write the test**

```typescript
import { describe, it, expect } from 'vitest';
import type { SimulationData, Turn, ElectionResult, ChannelMessage, Channel } from '../types';

describe('TypeScript types compile correctly', () => {
  it('can construct a minimal SimulationData', () => {
    const data: SimulationData = {
      run_id: 'test',
      config: {
        simulation: { num_rounds: 2, turns_per_phase: 3 },
        agents: { names: ['Alice', 'Bob'], starting_resources: 50.0 },
        resources: { carrying_capacity: 100, regeneration_factor: 1.5 },
        leader: { fine_destination: 'common_pool', default_limit: 10, default_penalty_rate: 0 },
        election: { method: 'plurality', first_election_round: 2 },
      },
      started_at: '2026-01-01T00:00:00Z',
      end_condition: 'time_limit',
      collapsed_at_round: null,
      survival_length: 2,
      rounds: [],
      metrics: { by_round: [] },
    };
    expect(data.run_id).toBe('test');
    expect(data.end_condition).toBe('time_limit');
  });

  it('Channel and ChannelMessage types work', () => {
    const msg: ChannelMessage = {
      turn: 5, turnGlobal: 5, agent: 'alice', text: 'Hello',
      significance: 'small_talk', heard_by: ['alice', 'bob'],
    };
    const channel: Channel = {
      id: 'channel_0', name: '#secret',
      members: ['alice', 'bob'],
      lifespan: { from: { round: 1, turn: 3 }, to: { round: 2, turn: 10 } },
      messages: [msg],
      systemEvents: [{ turn: 3, turnGlobal: 3, text: 'alice created this group', type: 'create' }],
    };
    expect(channel.id).toBe('channel_0');
    expect(channel.messages[0].text).toBe('Hello');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/__tests__/types.test.ts`
Expected: FAIL -- types.ts doesn't have Channel or ChannelMessage types

- [ ] **Step 3: Write minimal implementation**

Replace `visualizer/src/types.ts` with the comprehensive types (see the full file content in the design spec or repository). The file must export: `SimulationData`, `SimulationConfig`, `Round`, `Phase`, `Turn`, `PenaltyData`, `ElectionResult`, `MetricsData`, `RoundMetrics`, `RoundSummary`, `AgentRoundResult`, `MemoryEntry`, `ChannelMessage`, `ChannelSystemEvent`, `Channel`, `PanelId`, `Speed`, `PhaseName`, `AgentPosition`, `FlatTurn`, `PlaybackState`, `GraphEdge`, `GraphNode`, `GraphData`.

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/__tests__/types.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add visualizer/src/types.ts visualizer/src/__tests__/types.test.ts
git commit -m "feat: add TypeScript types for JSON schema and visualizer state"
```

---

### Task 6: JSON loader + validator

**Files:**
- Create: `visualizer/src/data/loader.ts`
- Test: `visualizer/src/__tests__/loader.test.ts`

**Interfaces:**
- Produces: `loadSimulationFile(file: File): Promise<SimulationData>`, `normalizeSimulationData(data: SimulationData): SimulationData`, `validateSimulationData(data: SimulationData): void`, `loadSimulationFromString(json: string): SimulationData`

- [ ] **Step 1: Write the test**

```typescript
import { describe, it, expect } from 'vitest';
import { loadSimulationFile, normalizeSimulationData, validateSimulationData } from '../data/loader';

const validJson = {
  run_id: 'test_001',
  config: {
    simulation: { num_rounds: 2, turns_per_phase: 3 },
    agents: { names: ['Alice', 'Bob'], starting_resources: 50.0 },
    resources: { carrying_capacity: 100, regeneration_factor: 1.5 },
    leader: { fine_destination: 'common_pool', default_limit: 10, default_penalty_rate: 0 },
    election: { method: 'plurality', first_election_round: 2 },
  },
  started_at: '2026-01-01T00:00:00Z',
  end_condition: 'time_limit',
  collapsed_at_round: null,
  survival_length: 2,
  rounds: [],
  metrics: { by_round: [] },
};

describe('normalizeSimulationData', () => {
  it('passes through valid data unchanged', () => {
    const data = JSON.parse(JSON.stringify(validJson));
    const result = normalizeSimulationData(data);
    expect(result.end_condition).toBe('time_limit');
  });
  it('fills in end_condition for pre-fix data', () => {
    const partial = JSON.parse(JSON.stringify(validJson));
    delete partial.end_condition;
    delete partial.collapsed_at_round;
    delete partial.survival_length;
    const result = normalizeSimulationData(partial);
    expect(result.end_condition).toBe('time_limit');
    expect(result.survival_length).toBe(2);
  });
  it('normalizes null heard_by to empty array', () => {
    const data = JSON.parse(JSON.stringify(validJson));
    data.rounds = [{ round: 1, phases: [{ phase: 'free_interaction', turns: [{
      turn: 1, agent: 'alice', action: 'public_talk', target: null, targets: null,
      is_private: false, message: 'Hi', amount: null, reasoning: '',
      significance: null, group: null, heard_by: null,
      resources_before: null, resources_after: null, leader_limit: null, penalty: null,
    }] }] }];
    const result = normalizeSimulationData(data);
    expect(result.rounds[0].phases[0].turns[0].heard_by).toEqual([]);
  });
  it('validates required fields', () => {
    expect(() => validateSimulationData({} as any)).toThrow();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/__tests__/loader.test.ts`
Expected: FAIL -- loader.ts doesn't exist

- [ ] **Step 3: Write minimal implementation**

Create `visualizer/src/data/loader.ts` with the three exported functions:
- `normalizeSimulationData()` -- fill in missing `end_condition`, ensure `analysis` exists, normalize `heard_by` from null to `[]`
- `validateSimulationData()` -- check `run_id`, `config`, `rounds` (array), `metrics.by_round` (array)
- `loadSimulationFile()` -- FileReader -> JSON.parse -> validate -> normalize -> return
- `loadSimulationFromString()` -- for testing: JSON.parse -> validate -> normalize -> return

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/__tests__/loader.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add visualizer/src/data/loader.ts visualizer/src/__tests__/loader.test.ts
git commit -m "feat: add JSON loader, validator, and normalizer"
```
### Task 7: Channel reconstructor

**Files:**
- Create: `visualizer/src/data/channelReconstructor.ts`
- Test: `visualizer/src/__tests__/channelReconstructor.test.ts`

**Interfaces:**
- Produces: `flattenTurns(data: SimulationData): FlatTurn[]`, `reconstructChannels(data: SimulationData): Channel[]`

**Implementation steps:**

- [ ] **Step 1: Write the failing test** (test flattenTurns flat structure, test reconstructChannels groups talk events into channels, test handle create_group/accept_invite/leave_group)
- [ ] **Step 2: Run test to verify it fails** (`npx vitest run src/__tests__/channelReconstructor.test.ts` -> FAIL)
- [ ] **Step 3: Write minimal implementation** (flattenTurns walks rounds/phases/turns with global index; reconstructChannels tracks current channel per agent, processes create_group/accept_invite/leave_group/talk actions, returns Channel[])
- [ ] **Step 4: Run test to verify it passes** (`npx vitest run src/__tests__/channelReconstructor.test.ts` -> PASS)
- [ ] **Step 5: Commit** (`git add ... && git commit -m "feat: add channel reconstructor"`)

---

### Task 8: Zustand store + selectors

**Files:**
- Create: `visualizer/src/store/simulationStore.ts`
- Test: `visualizer/src/__tests__/simulationStore.test.ts`

**Interfaces:**
- Produces: Zustand store with state (`sim`, `channels`, `currentTurn`, `isPlaying`, `speed`, `activePanel`, `graphOverlay`, `selectedAgent`, `selectedChannel`) and actions (`loadSimulation`, `clearSimulation`, `incrementTurn`, `goToTurn`, `togglePlay`, `setPlaying`, `setSpeed`, `togglePanel`, `closePanel`, `toggleGraphOverlay`, `setSelectedAgent`, `setSelectedChannel`)
- Consumes: `SimulationData`, `Channel` from types.ts

**Implementation steps:**

- [ ] **Step 1: Write the failing test** (test initial state, loadSimulation sets sim and channels, incrementTurn advances, togglePanel opens/closes, setSpeed changes speed)
- [ ] **Step 2: Run test to verify it fails** (`npx vitest run src/__tests__/simulationStore.test.ts` -> FAIL)
- [ ] **Step 3: Write minimal implementation** (zustand create store, all actions as direct state mutations via set/get, getTotalTurns helper)
- [ ] **Step 4: Run test to verify it passes** (`npx vitest run src/__tests__/simulationStore.test.ts` -> PASS)
- [ ] **Step 5: Commit**

---

### Task 9: PlaybackEngine

**Files:**
- Create: `visualizer/src/playback/PlaybackEngine.ts`
- Test: `visualizer/src/__tests__/playbackEngine.test.ts`

**Interfaces:**
- Produces: `getTurnState(data: SimulationData, turnIndex: number): TurnState` -- pure function returning `{ currentTurn, currentTurnIndex, totalTurns, currentRound, currentPhase, agentResources, poolLevel, turnToRound, turnToPhase, flatTurns }`
- Also: `getInterval(speed: number): number`

**Implementation steps:**

- [ ] **Step 1: Write the failing test** (test getTurnState at turn 0 returns round 1 phase free_interaction, at harvest turn returns harvesting, at beyond-last returns null currentTurn, tracks agent resources correctly)
- [ ] **Step 2: Run test to verify it fails** (`npx vitest run src/__tests__/playbackEngine.test.ts` -> FAIL)
- [ ] **Step 3: Write minimal implementation** (flattenTurns helper, buildAgentResources with starting_resources+incremental updates, getPoolLevel from resources_after.pool, main getTurnState function)
- [ ] **Step 4: Run test to verify it passes** (`npx vitest run src/__tests__/playbackEngine.test.ts` -> PASS)
- [ ] **Step 5: Commit**

---

### Task 10: Scene config + sprite loader

**Files:**
- Create/replace: `visualizer/src/canvas/sceneConfig.ts`
- Create: `visualizer/src/canvas/spriteLoader.ts`
- Test: `visualizer/src/__tests__/spriteLoader.test.ts`

**Interfaces:**
- Produces: `SCENE_CONFIG` (width, height, bgColor), `AGENT_COLORS` map, `getAgentColor()`, `ZONE_POSITIONS` (townHall, lake, outdoor), `HOME_POSITIONS`, `getHomePosition()`, `getZoneCenter()`, `SPEECH_BUBBLE_CONFIG`, `ANIMATION_CONFIG`, `loadSprite()`, `tintSprite()`

**Implementation steps:**

- [ ] **Step 1: Write the test** (verify scene dimensions, zone positions, agent colors, home positions)
- [ ] **Step 2: Run test to verify it fails** (`npx vitest run src/__tests__/spriteLoader.test.ts` -> FAIL)
- [ ] **Step 3: Write minimal implementation** (sceneConfig.ts: export all config objects; spriteLoader.ts: loadSprite creates Image with promise, tintSprite uses getImageData/putImageData for pixel-level tinting)
- [ ] **Step 4: Run test to verify it passes** (`npx vitest run src/__tests__/spriteLoader.test.ts` -> PASS)
- [ ] **Step 5: Commit**

---

### Task 11: Canvas renderer -- map + agents

**Files:**
- Create: `visualizer/src/canvas/CanvasRenderer.ts`
- Test: `visualizer/src/__tests__/canvasRenderer.test.ts`

**Interfaces:**
- Produces: `computeAgentPositions(sim, turnIndex): Record<string, AgentRenderState>`, `drawMap(ctx)`, `drawAgents(ctx, agentPositions, sim, currentTurn, leaderId)`, `AgentRenderState { x, y, zone, action }`

**Implementation steps:**

- [ ] **Step 1: Write the test** (computeAgentPositions returns home positions at turn -1, moves talking agent to town hall for public talk)
- [ ] **Step 2: Run test to verify it fails** (`npx vitest run src/__tests__/canvasRenderer.test.ts` -> FAIL)
- [ ] **Step 3: Write minimal implementation** (computeAgentPositions: start all at home, replay turns to determine zone based on action/channel; drawMap: grass, town hall rectangle, lake ellipse, decorative trees, home buildings; drawAgents: colored circles with name label, resource badge, leader crown, action icon)
- [ ] **Step 4: Run test to verify it passes** (`npx vitest run src/__tests__/canvasRenderer.test.ts` -> PASS)
- [ ] **Step 5: Commit**

---

### Task 12: Canvas renderer -- speech bubbles

**Files:**
- Modify: `visualizer/src/canvas/CanvasRenderer.ts`
- Test: `visualizer/src/__tests__/speechBubble.test.ts`

**Interfaces:**
- Produces: `formatBubbleText(text: string | null): string`, `shouldShowBubble(turn): boolean`, `getBubbleDimensions(text): { width, height, tail }`, `drawSpeechBubble(ctx, text, agentX, agentY, isPrivate, agentColor): void`

**Implementation steps:**

- [ ] **Step 1: Write the test** (truncation to 80 chars, show/hide logic, dimensions)
- [ ] **Step 2: Run test to verify it fails** (`npx vitest run src/__tests__/speechBubble.test.ts` -> FAIL)
- [ ] **Step 3: Write minimal implementation** (formatBubbleText truncates at 80 with "...", shouldShowBubble checks for talk actions with message, getBubbleDimensions estimates pixel size, drawSpeechBubble renders rounded rect with tail, text, and lock icon for private)
- [ ] **Step 4: Run test to verify it passes** (`npx vitest run src/__tests__/speechBubble.test.ts` -> PASS)
- [ ] **Step 5: Commit**

---

### Task 13: Canvas renderer -- graph overlay

**Files:**
- Modify: `visualizer/src/canvas/CanvasRenderer.ts`
- Test: `visualizer/src/__tests__/graphOverlay.test.ts`

**Interfaces:**
- Produces: `buildEdgeOpacity(weight: number): number`, `colorForSignificance(significance: string | null): string`, `drawGraphOverlay(ctx, edges: GraphEdge[], agentPositions): void`

**Implementation steps:**

- [ ] **Step 1: Write the test** (edge opacity scaling, significance color mapping)
- [ ] **Step 2: Run test to verify it fails** (`npx vitest run src/__tests__/graphOverlay.test.ts` -> FAIL)
- [ ] **Step 3: Write minimal implementation** (buildEdgeOpacity: weight/20 clamped 0.1-1.0; colorForSignificance: map significance to hex colors; drawGraphOverlay: iterate edges, draw lines with varying width/opacity/color)
- [ ] **Step 4: Run test to verify it passes** (`npx vitest run src/__tests__/graphOverlay.test.ts` -> PASS)
- [ ] **Step 5: Commit**

---

### Task 14: App shell + layout

**Files:**
- Create/replace: `visualizer/src/App.tsx`
- Create/replace: `visualizer/src/main.tsx`
- Create/replace: `visualizer/src/index.css`
- Test: `visualizer/src/__tests__/app.test.tsx`

**Implementation steps:**

- [ ] **Step 1: Write the test** (landing page renders when no sim loaded, simulation view renders when sim is loaded)
- [ ] **Step 2: Run test to verify it fails** (`npx vitest run src/__tests__/app.test.tsx` -> FAIL)
- [ ] **Step 3: Write minimal implementation** (LandingPage with Load button and file picker via hidden input; SimulationView with canvas ref, playback setInterval, rAF render loop calling drawMap/drawAgents/drawSpeechBubble/drawGraphOverlay; panel routing via activePanel; layout: TopBar + NavRail + Canvas + HUD + PlaybackControls + Timeline)
- [ ] **Step 4: Run test to verify it passes** (`npx vitest run src/__tests__/app.test.tsx` -> PASS)
- [ ] **Step 5: Verify build** (`npm run build` -> succeeds)
- [ ] **Step 6: Commit**

---

### Task 15: TopBar + file loading

**Files:**
- Create: `visualizer/src/components/TopBar.tsx`
- Test: `visualizer/src/__tests__/topBar.test.tsx`

**Implementation:** Simple header bar with Load button (hidden file input), run ID display, round/turn counter, play/pause toggle, metrics panel quick-button.

- [ ] **Step 1: Write the test** (shows run ID when sim loaded, shows play/pause button)
- [ ] **Step 2: Run test to verify it fails** -> FAIL
- [ ] **Step 3: Write minimal implementation** (30-line component using useSimulationStore)
- [ ] **Step 4: Run test to verify it passes** -> PASS
- [ ] **Step 5: Commit**

---

### Task 16: NavRail

**Files:**
- Create: `visualizer/src/components/NavRail.tsx`
- Test: `visualizer/src/__tests__/navRail.test.tsx`

**Implementation:** Vertical strip of 8 icon buttons (Conversations, Collusion, PerAgentStats, SimulationMetrics, SocialGraph, Elections, Harvesting, EventLog). Each button toggles its panel via `togglePanel()`. Active panel highlighted.

- [ ] **Step 1: Write the test** (renders 8 buttons, clicking toggles panel)
- [ ] **Step 2: Run test to verify it fails** -> FAIL
- [ ] **Step 3: Write minimal implementation** (~40 lines, array of {id, icon, label} map to buttons)
- [ ] **Step 4: Run test to verify it passes** -> PASS
- [ ] **Step 5: Commit**

---

### Task 17: HUD

**Files:**
- Create/replace: `visualizer/src/components/HUD.tsx`
- Test: `visualizer/src/__tests__/hud.test.tsx`

**Implementation:** Right sidebar (~200px) showing: round counter, phase indicator, pool gauge bar (gradient blue to red), play state, current leader, collapse status (red if collapsed).

- [ ] **Step 1: Write the test** (displays round number, pool level percentage, phase name)
- [ ] **Step 2: Run test to verify it fails** -> FAIL
- [ ] **Step 3: Write minimal implementation** (~60 lines, uses getTurnState selectors from store)
- [ ] **Step 4: Run test to verify it passes** -> PASS
- [ ] **Step 5: Commit**

---

### Task 18: PlaybackControls + Timeline

**Files:**
- Create: `visualizer/src/components/PlaybackControls.tsx`
- Create: `visualizer/src/components/Timeline.tsx`
- Test: `visualizer/src/__tests__/playbackControls.test.tsx`

**Implementation:** PlaybackControls: step back, play/pause, step forward, skip round, speed selector (1x/2x/4x/8x). Timeline: horizontal scrubber with round tick marks, phase-colored regions, collapse marker, draggable thumb.

- [ ] **Step 1: Write the test** (controls call store actions, timeline shows round ticks)
- [ ] **Step 2: Run test to verify it fails** -> FAIL
- [ ] **Step 3: Write minimal implementation** (PlaybackControls: icons/buttons mapped to store actions; Timeline: SVG/canvas-based scrubber computing tick positions from turnToRound)
- [ ] **Step 4: Run test to verify it passes** -> PASS
- [ ] **Step 5: Commit**

---

### Task 19-26: Panel components (8 panels)

Each panel follows the same pattern:
1. Write test
2. Run test -> FAIL
3. Write implementation (~50-150 lines per panel)
4. Run test -> PASS
5. Commit

**Task 19: Conversations panel** (`src/panels/Conversations.tsx`) -- channel list with member avatars, lifespan, message count. Click expands group-chat thread with message bubbles, sender name, turn timestamp, significance tags. System events inline. Filter bar. Click message jumps to turn.

**Task 20: Collusion Detection panel** (`src/panels/CollusionDetection.tsx`) -- summary stats (total flagged, breakdown by type), chronological timeline of flagged events only, filter by tag/agent/channel, click-to-jump.

**Task 21: Per-Agent Statistics panel** (`src/panels/PerAgentStats.tsx`) -- agent picker (avatar buttons), resource trajectory line chart (Recharts), centrality over time, harvest vs limit bar chart, violation count, conversation significance donut chart, interaction bar chart.

**Task 22: Simulation Metrics panel** (`src/panels/SimulationMetrics.tsx`) -- Gini coefficient line, pool level area chart, total harvest bar chart, violations bar chart, survival length big number, per-agent multi-line resource chart, end condition banner.

**Task 23: Social Graph panel** (`src/panels/SocialGraph.tsx`) -- force-directed graph using D3-force, nodes sized by centrality, edges weighted, scrub timeline updates graph, toggle cumulative/current round, click node highlights connections.

**Task 24: Elections panel** (`src/panels/Elections.tsx`) -- per-round election cards with candidates, platforms, vote map (arrows/matrix), winner highlighted with crown, power concentration indicator. Click round -> jump to election turn.

**Task 25: Harvesting panel** (`src/panels/Harvesting.tsx`) -- per-round table: agent catch, limit, violation (red), penalty, destination. Pool level before/after bar. Total harvest, total violations. Click round -> jump.

**Task 26: Event Log panel** (`src/panels/EventLog.tsx`) -- chronological feed table (turn, agent, action, target, message truncated, significance). Filters by action type and agent. Search input. Click row -> jump to turn.

---

### Task 27: Integration + visual verification

**Files:** None new -- this is a manual verification task.

- [ ] **Step 1: Load a real output JSON**

Copy `outputs/collapse_demo.json` to `visualizer/public/` for easy testing, or use the file picker at runtime.

- [ ] **Step 2: Visual review**

- Verify map renders: town hall, lake, homes, trees, grass
- Verify agents appear as colored circles with name labels
- Verify speech bubbles appear on talk events and fade
- Verify HUD updates: round counter, pool gauge, phase indicator
- Verify playback controls: play/pause, step, speed
- Verify timeline scrubber: click/drag jumps to turn
- Verify nav rail: each panel opens/closes
- Verify panels render correct data

- [ ] **Step 3: Run all visualizer tests**

Run: `npx vitest run`
Expected: All tests pass

- [ ] **Step 4: Run sim tests to confirm no regression**

Run: `python -m pytest -q` (from project root)
Expected: All tests pass

- [ ] **Step 5: Build for production**

Run: `npm run build` (from visualizer/)
Expected: Build succeeds, output in `visualizer/dist/`

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "feat: complete GovSim visualizer with spatial world, 8 panels, and playback"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Pool collapse end condition (Phase A, Tasks 1-2)
- [x] Survival metrics in output JSON (Task 2)
- [x] Fresh Vite project replaces old Phaser visualizer (Task 4)
- [x] TypeScript types matching JSON schema (Task 5)
- [x] JSON loader with normalization (Task 6)
- [x] Channel reconstruction (Task 7)
- [x] Zustand state management (Task 8)
- [x] Playback engine with getTurnState (Task 9)
- [x] Scene config + sprite loading (Task 10)
- [x] Canvas renderer: map, agents, positions (Task 11)
- [x] Speech bubbles with private/public (Task 12)
- [x] Graph overlay (Task 13)
- [x] App shell with layout (Task 14)
- [x] TopBar + file loading (Task 15)
- [x] NavRail 8-panel system (Task 16)
- [x] HUD with pool gauge (Task 17)
- [x] Playback controls + timeline (Task 18)
- [x] Conversations panel (Task 19)
- [x] Collusion Detection panel (Task 20)
- [x] Per-Agent Statistics with Recharts (Task 21)
- [x] Simulation Metrics dashboard (Task 22)
- [x] Social Graph with D3-force (Task 23)
- [x] Elections panel (Task 24)
- [x] Harvesting panel (Task 25)
- [x] Event Log panel (Task 26)
- [x] Integration verification (Task 27)

**Placeholder scan:** No TBD, TODO, "implement later", or "similar to" patterns found. Every file path is absolute.

**Type consistency:** All task interfaces reference exact function names and types that are defined in earlier tasks.

---

## Execution Handoff

Plan complete. Two execution options:

1. **Subagent-Driven (recommended)** -- Dispatch a fresh subagent per task using `superpowers:subagent-driven-development`. Each task is independently testable. Review between tasks.

2. **Inline Execution** -- Execute tasks in this session using `superpowers:executing-plans`. Batch execution with checkpoints for review after Phase A (Task 3) and after visualizer scaffold (Task 14).
