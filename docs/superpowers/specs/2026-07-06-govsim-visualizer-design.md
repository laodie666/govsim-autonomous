# GovSim-Autonomous Visualizer — Design Spec

**Date:** 2026-07-06
**Status:** Approved (pending user review of written spec)
**Location:** `govsim-autonomous/visualizer/` (old visualizer deleted, fresh project)

## Goal

Build a new, eye-catching visualizer for GovSim-Autonomous simulations. Present GovsimElect-style simulations in a visually pleasing, Smallville-inspired way that clearly shows agent interaction, communication (one-on-one, small group, broadcast), technical metrics, and emergent collusion/power dynamics. The current visualizer is broken (Phaser 4 API mismatch, blank canvas) and is being replaced entirely.

**Key principle:** The simulation is ours to modify. If the visualizer needs a field that doesn't exist in the output JSON, we extend the sim rather than working around its absence. The output schema is a moving target, not a fixed contract.

## Build Approach

**Two phases, sequential:**

### Phase A — Sim Fix (prerequisite)
Add a pool-collapse end condition to the simulation engine. Currently the sim runs a fixed `num_rounds` loop and never ends early — the pool can hit 0 during harvesting but `regenerate()` floors it at 5% capacity, so it bounces back. This makes "survival length" meaningless.

**Fix:**
- In `engine.py`, after the harvesting phase, check if `pool.amount == 0`. If so, end the simulation immediately (break the round loop before regeneration).
- Add to output JSON (via `recorder.py`):
  ```json
  {
    "end_condition": "collapse" | "time_limit",
    "collapsed_at_round": 12 | null,
    "survival_length": 12
  }
  ```
- The 5% regen floor in `resource_pool.py` stays as a safety net for regeneration, but the engine checks for collapse *before* regen runs.
- Add tests covering the collapse path.
- Small change: ~20 lines in `engine.py` + a recorder field + tests.

### Phase B — New Visualizer (fresh project)
Delete the old `visualizer/` directory. Build a new standalone React + TypeScript + Vite app from scratch.

---

## Architecture

### Tech Stack
- **React 19 + TypeScript + Vite** — UI chrome, panels, state, routing
- **HTML5 Canvas (2D context)** — the spatial world only, drawn imperatively via `requestAnimationFrame`
- **Tailwind CSS** — styling, responsive layout, visual polish
- **Zustand** — lightweight state management (current turn, playback, loaded sim)
- **Recharts** — charts in the metrics overlay and per-agent stats
- **D3-force** (optional) — for the social graph panel force layout

### Top-Level Layout

```
┌─────────────────────────────────────────────────────────────┐
│  TopBar:  [≡] Run: sim_xxx   Round 3/12  Phase: Harvesting  │
│                                       ▶ Play    [Metrics]   │
├──┬─────────────────────────────────────────────────────┬────┤
│N │                                                      │ H  │
│a │                                                      │ U  │
│v │           Canvas (Spatial World)                     │ D  │
│  │      — town map, agents, speech bubbles              │    │
│R │      — graph overlay (toggle with G)                │    │
│a │                                                      │    │
│i │                                                      │    │
│l │                                                      │    │
├──┴─────────────────────────────────────────────────────┴────┤
│  Playback:  ◀◀ ◀ ▶ ▶▶  ──●─── timeline  1x  2x  4x  [G]raph│
└─────────────────────────────────────────────────────────────┘
```

When a nav icon is clicked, a panel slides over from the left (canvas dims but stays visible):
```
┌──────────────┬───────────────────────────────────────┬────┐
│              │ ░░░░░░░░░░░░░░ (canvas dimmed) ░░░░░░ │ H  │
│  Slide-over  │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │ U  │
│  Panel       │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │ D  │
│              │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │    │
└──────────────┴───────────────────────────────────────┴────┘
```

### Navigation Rail (left, ~56px)
Vertical strip of icon buttons. Active icon highlighted. Clicking toggles its panel open/closed. Panels slide over from the left, canvas dims but stays visible. Close with `Esc` or clicking the nav icon again.

| Icon | Panel | Purpose |
|------|-------|---------|
| 💬 | Conversations | Channel browser — group-chat archive per channel |
| 🕵️ | Collusion Detection | Flagged messages (collusion/deal/betrayal/alliance) timeline |
| 📊 | Per-Agent Statistics | Agent picker → resource trajectory, centrality, harvest, violations |
| 📈 | Simulation Metrics | Full experiment results dashboard (Gini, pool, harvest, survival) |
| 🌐 | Social Graph | Force-directed network view, scrub-driven |
| 🏛️ | Elections | Per-round election results, platforms, votes, power concentration |
| 🎣 | Harvesting | Per-round harvest breakdown, violations, penalties |
| 📜 | Event Log | Raw chronological feed of every turn, filterable |

### Minimal HUD (right, always-on, ~200px)
- Round counter: `Round 3 / 12`
- Phase indicator: `Phase: Harvesting`
- Pool gauge: visual bar (gradient blue → empty) with numeric `37.5 / 100 fish`
- Play state: `▶ Playing 2x` or `⏸ Paused`
- Current leader: `Leader: Kate` (or `No leader` round 1)
- Collapse status: `⚠ COLLAPSED at round 8` (red, if applicable) or `Surviving`

### TopBar
- Load File button (or drag-and-drop anywhere)
- Run ID display
- Play/pause + speed (duplicated from bottom bar for convenience)
- Metrics quick-button (opens 📈 panel)

### Bottom Bar
- Playback controls: step back, play/pause, step forward, skip round
- Timeline scrubber: round boundaries as tick marks, collapse point as red marker
- Speed: 1x / 2x / 4x / 8x
- Graph toggle (`G`)

---

## The Spatial World (Canvas)

A Smallville-inspired town map. The heart of the visualizer.

### Map Layout
```
┌─────────────────────────────────────────────────────────┐
│  🏠Kate    🏠Jack      ╭──── Town Hall ────╮   🌳  🌳   │
│                         │   (public zone)  │             │
│   🌳                    │  ●Emma ●Luke      │      🌳     │
│                         │  ●Kate ●Jack      │             │
│   🏠Emma   🏠Luke       ╰──────────────────╯   🌳       │
│                                                         │
│        🌳  🌳     [private convos happen out here]       │
│                   ●Kate+Luke huddled by a tree          │
│                                                         │
│   ~~~~~ Lake ~~~~~ (edge of map, fishing destination)   │
└─────────────────────────────────────────────────────────┘
```

- **Town Hall** — large central building. All agents in the `public` channel congregate here. Public speeches, broadcasts, and elections happen inside.
- **Homes** — each agent has a house on the map (fixed position, labeled). At round start and during reflection phases, agents are at home. They walk to Town Hall when free-interaction begins.
- **Lake** — at the edge of the map. Agents walk here to fish during harvesting. Water level drops as pool depletes. Goes dry (cracked-earth) on collapse.
- **Outdoors** — space between homes and Town Hall. Private conversations happen here — agents leave Town Hall together and find an empty spot (by a tree, in a corner) to huddle. When the channel dissolves, they walk back.

### Agents
- Colored circles or character sprites (each agent gets a stable color/tint).
- Name label below. Resource count as a small badge.
- Leader gets a crown icon or gold ring.
- Current action shown as a tiny icon over the agent (💬 talking, 🎣 fishing, 🗳️ voting, 🚶 moving).
- Acting agent gets a subtle highlight glow so you know whose turn it is.

### Agent Movement
When an agent changes channel (create_group, accept_invite, leave_group), they smoothly animate from current position to the new zone. Easing over ~500ms. This is the Smallville "you can see them walk over" feel.

### Speech Bubbles (live)
- When an agent talks, a speech bubble appears above them with a tail.
- Bubble shows message text (truncated to ~80 chars; full text on hover/click).
- Bubble color matches the agent's color.
- **Private vs public:** public bubbles are white/solid; private-channel bubbles are tinted/semi-transparent with a 🔒 icon. Only agents in that channel see the bubble render.
- Bubble fades after ~3 seconds or when the next agent acts.
- **Click a live bubble** → opens Conversations panel, scrolled to that message in its channel thread, current message highlighted.

### Graph Overlay (toggle with `G`)
- Semi-transparent lines between agents who have communicated (cumulative up to current turn).
- Line thickness = number of interactions.
- Color encodes relationship type (collusion-tagged = red, normal = gray).
- Draws on top of the spatial scene without obscuring it.

### Camera/Zoom
Canvas supports pan and zoom (scroll to zoom, drag to pan) for future 100-agent scaling. Fit-to-screen by default.

### Sprites
**Source: Kenney CC0 packs (no attribution required)**
- **Kenney RPG Urban Kit** — 480+ sprites: buildings, roads, 6 characters with 4-direction walk animations, fences, street furniture. URL: https://kenney.nl/assets/rpg-urban-pack
- **Kenney Foliage Pack** — 100+ nature sprites (trees, bushes, flowers, rocks). URL: https://kenney.nl/assets/foliage-pack
- **Water/lake** — draw on canvas (animated blue tiles) or pull from PicoVillage pack.
- **Town Hall** — PicoVillage has one (https://zealxy.itch.io/picovillage-tileset), or scale up a Kenney building and label it.

**Character tinting:** load Kenney character spritesheets into canvas, use `getImageData()` to replace color ranges per agent. Each agent gets a unique tint while sharing the same base walk-cycle sprites.

---

## Playback & Timeline

**Turn-based, not real-time.** The simulation is a sequence of discrete turns. Playback steps through turns one at a time.

### Playback States
- **Paused** (default on load) — shows turn 0 (initial state, agents at home)
- **Playing** — advances one turn every `interval` ms, where `interval = base / speed`
- **Stepping** — manual ◀ / ▶ advances one turn

### Speed Control
1x / 2x / 4x / 8x. At 1x, ~1500ms per turn (enough to read a bubble). At 8x, ~190ms (fast skim). Optional "skip pass" toggle to auto-skip `pass` turns.

### Timeline Scrubber
```
Round 1          Round 2          Round 3    ⚠collapse
│                │                │          │
●──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┤
   1  2  3  4  5  6  7  8  9 10 11 12 13 14 15
                                              ▲ current
```
- One tick per turn. Round boundaries as vertical lines with labels.
- Collapse point marked red ⚠ (if applicable).
- Drag to scrub — jumps to any turn, all views update.
- Phase regions color-coded (free interaction = light blue, election = yellow, harvesting = green).

### Per-Turn Playback Behavior
1. Advance turn index → load event
2. Update agent positions (animate channel switches)
3. Show the action:
   - `talk` → speech bubble
   - `fish` → walk to lake, fish animation, pool updates, walk back
   - `vote`/`nominate` → election icon, ballot animation in Town Hall
   - `transfer` → arrow sender → receiver with fish icon
   - `pass` → subtle dim pulse (or nothing if skip-pass on)
4. Update HUD (pool, round, phase, leader, resources)
5. Update graph overlay (if on)
6. Update channel sidebar (if open) — highlight current message

### Round Transitions
Brief overlay announces "Round 2 — Election Round". Pool regenerates (lake visually refills). Agents return home for reflection, then walk back to Town Hall.

### Jump-to from Panels
Clicking a message in Conversations, a flagged event in Collusion Detection, or a data point in any chart jumps the scrubber to that turn and pauses.

---

## Panel Contents

### 💬 Conversations
- **Top:** list of all channels that ever existed — `#public`, `#channel_0`, `#channel_1`… Each row: channel name, member avatars, lifespan (`Turn 3–14`), message count, colored dot if flagged.
- **Click a channel →** group-chat thread: messages in order, sender avatar + name, turn number as timestamp, message text, significance tag badge. System events inline and styled differently: *"Kate created this group"*, *"Luke joined"*, *"Emma left"*, *"Kate returned to #public"*. Filter bar: filter by significance label.
- **Click a message →** timeline jumps to that turn, panel closes, canvas shows spatial state.

### 🕵️ Collusion Detection
- **Top:** summary stats — total flagged messages, breakdown by significance type, which channels had most flagged activity, which agents appear most in flagged messages.
- **Below:** chronological timeline of flagged events only. Each entry: turn, channel, agents involved, message excerpt, significance tag. Color-coded (collusion = red, betrayal = dark red, deal = gold, alliance = purple, economic = green).
- **Filter** by tag, agent, channel. Click → jump to turn.

### 📊 Per-Agent Statistics
- **Top:** agent picker (avatar buttons).
- **For selected agent:**
  - Resource trajectory — line chart (fish over all rounds)
  - Centrality over time — line chart (degree centrality per round)
  - Harvest vs. limit — bar chart per round (harvest, limit line, violation highlighted red)
  - Violation count — number summary
  - Conversation significance breakdown — donut chart
  - Who they talked to most — mini bar chart of interaction counts per other agent
  - Channels they were in — list with turn ranges

### 📈 Simulation Metrics
Full experiment results dashboard:
- Gini coefficient over time (line chart, collapse marker if applicable)
- Pool level over time (area chart, depleting)
- Total harvest per round (bar chart)
- Violations per round (bar chart)
- Survival length — big number: "Survived 12 rounds" or "⚠ Collapsed at round 8"
- Per-agent resource trajectories — multi-line chart (all agents)
- End condition banner: green "Reached time limit" or red "Pool collapsed"

### 🌐 Social Graph
Full network view (larger than canvas overlay). Force-directed graph:
- Nodes = agents, sized by centrality, colored by current channel
- Edges weighted by interaction count (cumulative up to current turn)
- Scrub timeline → graph updates live
- Toggle: "current round only" vs "cumulative"
- Edge color by significance (collusion edges red)
- Click node → highlight that agent's connections, dim others

### 🏛️ Elections
Per-round election cards. For each election round:
- Candidates with platforms (harvest limit, penalty rate, campaign message)
- Vote map: who voted for whom (arrows or matrix)
- Winner highlighted, crown icon
- Power concentration indicator: "Same leader as last round" or "New leader"
- Click round → jump to that election turn

### 🎣 Harvesting
Per-round harvest breakdown table:
- Each agent's catch amount, the limit, violation (red row), penalty imposed, penalty destination
- Pool level before → after (visual bar)
- Total harvest, total violations
- Click round → jump to harvest phase

### 📜 Event Log
Raw chronological feed of every turn, all action types. Columns: turn, agent, action, target, message (truncated), significance. Filterable by action type and agent. Searchable. Click row → jump to turn.

---

## Data Flow & State Management

### Loading
User clicks "Load File" or drags JSON onto window → file reader parses → `loader.ts` validates schema (checks for `rounds`, `metrics`, `round_summaries`). Invalid → toast error. Valid → populate Zustand store, reset to turn 0, render initial state (agents at home).

Loader normalizes: ensures `heard_by` is an array (may be `null` in stub runs), fills `analysis` as `{}` if missing, derives `end_condition` as `"time_limit"` if absent (pre-fix runs).

### State (Zustand store)
```
store = {
  sim: SimulationData,
  channels: ReconstructedChannel[],
  currentTurn: number,
  isPlaying: boolean,
  speed: 1 | 2 | 4 | 8,
  activePanel: PanelId | null,
  graphOverlay: boolean,
  selectedAgent: string | null,
  selectedChannel: string | null,
}
```
Derived state (currentRound, currentPhase, currentMetrics, agentPositions, visibleMessages) is computed via selectors on `currentTurn` — not stored.

### PlaybackEngine
Pure function: `getTurnState(sim, turnIndex) → { round, phase, agentPositions, channels, visibleMessages, metrics }`. No side effects, testable. Playback loop increments `currentTurn` every `interval` ms when playing. Stops at last turn or collapse point.

### Canvas Renderer
Subscribes to `currentTurn` + `agentPositions` + `visibleMessages` + `graphOverlay`. Owns its own `requestAnimationFrame` loop for smooth movement — when an agent's target position changes, it tweens over ~500ms regardless of playback speed. Loads sprite sheets once at init. Draws map from static layout config. Draws agents at tweened positions. Draws speech bubbles. Draws graph edges if overlay on.

### Channel Reconstruction (`channelReconstructor.ts`)
Walks the turn sequence, tracking each agent's current channel. Emits `Channel[]`: each with `id`, `members` (with join/leave turn ranges), `messages` (talk events with turn + heard_by), `lifespan`. The engine already records `heard_by` per turn, so reconstruction is grouping, not inferring.

### Error Handling
- **Missing fields** (stub runs, pre-fix runs): loader fills defaults, visualizer degrades gracefully.
- **No `analysis` field** (stub mode): Collusion Detection shows "No conversation analysis available (stub run)".
- **No `end_condition` field**: treated as `"time_limit"`, survival length = `num_rounds`.
- **Malformed JSON**: loader rejects, toast error.
- **Empty message fields** (`pass` turns): no bubble, subtle dim pulse.

### Testing
- Unit tests for `loader.ts`, `channelReconstructor.ts`, `PlaybackEngine`, panel data selectors. Vitest.
- Canvas renderer tested via data it receives, not pixels.
- Use existing 49 output JSONs in `outputs/` as test fixtures.

### Project Structure
```
visualizer/
├── src/
│   ├── App.tsx                  # Root, layout, panel routing
│   ├── store/                   # Zustand store + selectors
│   ├── data/                    # loader.ts, channelReconstructor.ts, catalogUtils.ts
│   ├── playback/                # PlaybackEngine.ts
│   ├── canvas/                  # CanvasRenderer.ts, spriteLoader.ts, sceneConfig.ts
│   ├── components/              # TopBar, NavRail, HUD, PlaybackControls, Timeline
│   ├── panels/                  # Conversations, Collusion, PerAgent, Metrics, Graph, Elections, Harvesting, EventLog
│   ├── charts/                  # Recharts wrappers (GiniChart, ResourceTrajectory, etc.)
│   ├── types.ts                 # TypeScript interfaces matching JSON schema
│   └── __tests__/               # Vitest
├── public/
│   └── sprites/                 # Kenney CC0 sprite PNGs
├── package.json
└── vite.config.ts
```

---

## Open Items / Future Considerations

- **100-agent scaling** — "worry about later" per user. Canvas + zoom/pan designed with this in mind but not optimized for it yet.
- **Live viewer** — currently post-hoc only. Could add WebSocket streaming later if desired.
- **Additional metrics** — the sim can be extended to output more metrics as needed (e.g., coalition stability, leader power index, trust network). The schema is extensible.
- **Sprite swap** — starting with Kenney CC0 packs; could upgrade to custom/AI-generated sprites later without changing the renderer architecture.
