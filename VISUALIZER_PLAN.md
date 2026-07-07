# GovSim Visualizer — Implementation Plan

## Overview

A visually immersive, interactive playback UI for GovSim autonomous multi-agent LLM simulations. Loads post-hoc JSON output files and renders the simulation as a living 2D world with agents, speech, fish pools, and analytical overlays.

**Tech stack:** React + Phaser.js (Phaser-in-React)
**Data flow:** `simulation → outputs/sim_<id>.json → File picker → Visualizer`

---

## Design Decisions (from grilling)

### Architecture
- **Phaser-in-React:** React owns layout (menus, HUD, dashboards). Phaser canvas is one React component.
- **File picker only:** No backend. User loads `.json` via browser FileReader API. No pre-bundled samples.
- **Empty state:** Minimal landing page with app title, "Load Simulation" button, brief info about GovSim and the visualizer.

### Simulation Fix (prerequisite)
- Add `heard_by: list[str]` and `group: str` to the output JSON at the source:
  - `simulation/recorder.py`: Add `heard_by` field to `EventOutput` and `record_event()` parameter
  - `simulation/engine.py`: Compute channel/heard_by before `record_event()` call, pass them instead of `group=None`
- This eliminates the need for the visualizer to reconstruct channel membership.

### Scene & Rendering
- **Primary view:** Smallville-style 2D world — agents in a shared space with a visible fish pool
- **Agent sprites:** Character illustrations (pixel-art / vector style) with state indicators:
  - Leader: crown/star icon
  - Private channel members: visual color aura or outline
  - Talking: speech bubble animation
  - Violations: temporary red flash
  - Fish count: small number indicator
- **Fish pool:** Physical pool in the scene that agents walk to when they fish. Water level changes visibly. HUD gauge shows precise pool status.
- **Conversation visualization:** Visual separation — agents in private channels physically move to a private zone on screen. This makes coalition formation obvious.
- **Speech bubbles:** Clickable — opens conversation transcript popup showing full thread with significance labels (collusion, deal, betrayal, alliance).
- **Graph view:** Analytical network graph in a separate menu (not an overlay). Shows interaction edges, channel clusters, centrality.

### Playback
- **Strict turn order:** One agent acts at a time. Turns play sequentially.
- **Controls:** Play/pause, step forward/back, round scrubber, speed control.

### Data Displays
- **HUD:** Per-agent fish counters, pool gauge
- **Metrics dashboard:** Gini coefficient, total harvest, penalties, pool level over time (per-round charts)
- **Conversation catalog:** Sidebar/menu with all past conversations, filterable by significance label
- **Timeline view:** Round-by-round overview of who talked to whom, group dynamics, resource changes
- **Technical metrics:** Survival length, violations, election results, centrality scores

---

## Implementation Phases

### Phase 0 — Simulation Fix (prerequisite)
1. Add `heard_by` to `EventOutput` dataclass in `simulation/recorder.py`
2. Add `heard_by` parameter to `recorder.record_event()`
3. In `engine.py:_handle_agent_turn()`, compute channel/heard_by before the recorder call, pass `group=channel, heard_by=list(heard_by)`
4. Run tests, generate a real DeepSeek sample output for development

### Phase 1 — Project Scaffold & Data Layer
1. Initialize React + Phaser project (Vite + React + phaser + react-phaser-fiber or manual integration)
2. Build data loading: file picker → JSON parser → typed data structures
3. Build channel state reconstruction from action stream (parser does this at load time)
4. Build `SimulationStore` — a context/provider holding the parsed simulation data
5. Verify by loading golden snapshot JSON and printing data to console

### Phase 2 — Phaser Scene (Core Rendering)
1. Phaser canvas component inside React
2. Agent sprites: colored character shapes with name labels
3. Fish pool: blue circle/ellipse that shrinks/grows based on pool level
4. Speech bubbles: talk messages render as timed bubbles above agents
5. Group zones: visual areas for public vs private channels
6. Agent movement: idle animation, walk-to-pool for fishing, walk-to-private-zone for private talk
7. Leader and violation indicators

### Phase 3 — Playback Controls (React)
1. Play/pause button
2. Round & turn scrubber (slider)
3. Step forward/backward
4. Speed control (1x, 2x, 5x)
5. Sync playback state with Phaser scene

### Phase 4 — HUD & Metrics Dashboard (React)
1. Per-agent resource counters
2. Fish pool gauge
3. Per-round Gini coefficient chart
4. Harvest totals (per-round + cumulative)
5. Penalties / violations summary
6. Pool level over time chart

### Phase 5 — Conversation Catalog & Graph Menu
1. Clickable speech bubbles → conversation transcript popup
2. Conversation catalog sidebar with significance labels and filters
3. Network graph view (Phaser or D3-based) showing interaction edges, centrality, channel clusters
4. Timeline view (round-by-round overview)

### Phase 6 — Polish & Edge Cases
1. Empty landing page with "Load Simulation" and info
2. Responsive layout (village scene + dashboard panels)
3. Loading states
4. Handle large files (100 agents, many rounds) — paginate/virtualize
5. Error handling for malformed JSON
6. Performance optimization (Phaser object pooling for many agents)

---

## Key Technical Notes

### Channel Routing (visualizer-side)
Even with `heard_by` in the JSON, the visualizer still needs to track **group membership per turn** for rendering agent positions (public zone vs private zone). This is reconstructed from the action stream:
- `create_group` → creator enters new channel
- `accept_invite` → accepter enters that channel
- `reject_invite` → nothing changes
- `leave_group` → agent returns to public

### Data the Visualizer Must Compute
- **Group membership timeline:** Who was in which channel at each turn
- **Social network edges:** Interaction frequency per agent pair (count of talk events between them)
- **Resource history per agent:** Aggregate from `resources_before`/`resources_after` across turns
- **Conversation threads:** Group consecutive talk events from same channel members

### Data Already in JSON
- Per-turn events with action, message, amounts, resources
- Gini coefficient per round
- Centrality scores per round
- Election results (winner, votes, voter_map)
- Analysis labels (turn → significance)
- Agent memories and round summaries
