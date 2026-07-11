# GovSim-Autonomous v2 — Design Spec

**Date:** 2026-07-07
**Status:** Draft (pending user review)
**Location:** `govsim-autonomous/simulation/` (existing files modified)
**Config:** `config/five_agents_drama.yaml` (new default)

## 1. Title & Overview

GovSim v2 is a rewrite of the autonomous multi-agent fishery simulation to turn it from a ceremonial default-penalty-rate-zero sandbox into a genuine social-dilemma game. Five LLM agents (John, Kate, Jack, Emma, Luke) fish a common pool over 3 rounds while a leader sets harvest policy. The core mechanics — ephemeral per-phase private channels, optional candidacy with a 5-fish sunk cost, secret-ballot elections every round, and a reflection phase — create incentives for lobbying, vote-buying, coalition formation, and betrayal. The simulation output feeds the visualizer (v1 spec, 2026-07-06) unchanged; the recorder schema is extended, not broken.

## 2. Motivation & Intent

### Motivation

The current v1 sim has 18 identified bugs and missing features. Most critically, `default_penalty_rate: 0.0` in `config.py:31` means the social dilemma is decorative — agents rationally harvest max and ignore the leader. Candidacy is forced (no cost, `engine.py:949-950`), channels persist across phases (no strategic reset), and prompts lack full context for harvest/vote/campaign decisions (prompts.py:96-124/127-152/155-193). The result is a simulation that runs but isn't *interesting* — no coalition dynamics, no trade-offs, no emergent strategy.

### Intent

The rewrite targets **"an interesting simulation using LLM calls"** — a system where agents use private channels to lobby, bribe, and form coalitions. The leader's power (set `harvest_limit` + `penalty_rate`) creates an implicit market for policy influence. Ephemeral channels force repeated coalition-formation. Secret ballots prevent vote-monitoring. A 5-fish candidacy cost creates a real participation decision. The pool-collapse condition (`pool.amount < 0.01`, was `== 0` — `engine.py:237`) ends runs dramatically. Every design choice below serves this goal.

## 3. Design Principles

1. **The leader's power is the leader's currency.** Policy-setting is the only reward for winning. There is no direct payoff — the payoff comes from agents paying (bribing, transferring) the leader to set favorable limits. This creates an implicit market that drives negotiation.

2. **Every phase is a fresh negotiation cycle.** Channels auto-dissolve at end of phase. Agents cannot hide in a permanent private group; they must repeatedly recruit and negotiate. Personal logs persist (memory survives), but the meeting room resets.

3. **Agents have a subjective voice, not an omniscient god-view.** Prompts exclude conversation analysis labels and LLM-generated omniscient summaries. The agent's own reflection text replaces the third-person summary. What the agent doesn't see or hear, it doesn't know.

4. **Systemic transparency for learning, channel opacity for strategy.** Transfers inside a private channel are invisible to outsiders (enabling secret vote-buying). Systemic events — who ran, who got fined — are public (enabling learning and reputation). This balance creates asymmetric information without breaking agent reasoning.

5. **Minimal engine changes, maximum payoff.** Most changes are targeted: new config values, channel dissolution logic, prompt context blocks, reflection phase plumbing. The architecture (engine → channels → recorder → LLM) stays unchanged. New features are wired in, not rewritten.

## 4. Game Theory & Config

### Configuration

```yaml
# config/five_agents_drama.yaml
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

### Motivation

- **3 rounds** (was 2 in `five_agents.yaml`): Enough for reputation to develop across rounds, short enough for rapid iteration. Round 1 establishes first interactions, round 2 is the midgame, round 3 is the endgame (last chance to defect).
- **5 agents** (John, Kate, Jack, Emma, Luke): Odd number prevents ties. 5 is the sweet spot for coalition formation (2+2+1 splits, 3-vote majorities) without overwhelming the LLM context window.
- **Starting resources: 20** (was 50): Lower starting fish makes the 5-fish candidacy cost painful — a real decision. Makes transfers more meaningful (giving 5 fish is a big deal).
- **Regen factor: 2.0** (was 1.5): Faster regen keeps the game alive through 3 rounds even with aggressive harvesting. Prevents trivial collapse in round 1.
- **Fish per harvest: 10, harvest limit: 10** (was 5/10): Higher default harvest means agents CAN exceed the limit meaningfully. The leader's choice of limit matters (set it low = fish for bribes, set it high = populist).
- **Penalty rate: 0.5** (was 0.0): The critical change. Excess fish × 0.5 taken from violator. High enough to hurt, low enough that exceeding the limit is sometimes worth it. Creates the core trade-off.
- **Fine destination: `common_pool`**: Penalties go back to the pool, not to the leader or distributed. This means penalty enforcement benefits everyone (common resource replenishment), creating a collective action problem around enforcement.
- **Candidacy cost: 5 fish** (new): Burned, sunk cost. If you can't pay, you can't run. Creates a real barrier to entry and a decision: "Do I spend 25% of my fish to maybe become leader?"
- **First election: round 1, every round**: Leadership is always at stake. Round 1 establishes the initial leader (pre-campaign lobbying becomes critical).

### Intent

Every config value is set to create genuine strategic tension. The 0.5 penalty rate means agents face a real trade-off between cooperation and defection. The 5-fish candidacy cost means running for office is a real investment. The 3-round horizon means the last round is a natural endgame where cooperation may break down. These values produce a simulation with emergent collusion, betrayal, and lobbying — not just agents saying "I fish 10 fish" in a loop.

## 5. Round Structure

```
Round N:
  1. Pre-election free_interaction   (10 turns)
  2. Election phase
       a. Campaign: candidates publicly state platform
       b. Voting: secret ballot
  3. Harvest phase                    (per-agent, sequential)
  4. Post-harvest free_interaction    (10 turns, debrief + early lobbying)
  5. Reflection phase                 (each agent reflects + plans)
  → End of round
```

### Motivation

The old structure was: free_interaction → election → harvesting → post-harvest interaction → reflection. The key changes are renaming and clarifying the two free interaction phases:

- **Pre-election free_interaction** (formerly just "free_interaction 1"): This is the lobbying phase. Channels form here for coalition-building, vote-trading, bribes. The election hasn't happened yet, so there's no winner — agents negotiate based on expected outcomes and personal relationships. They see campaign platforms from candidates who announced (candidates publicly state their platform at the start of this phase, then agents lobby around it).

- **Post-harvest free_interaction** (formerly "free_interaction 2"): This is the debrief phase. The election is over, harvest is done. Agents know the leader's actual policy, saw who got penalized, and have a full round of experience. This phase serves two purposes: (1) post-hoc accountability ("you promised X but did Y") and (2) early next-round lobbying (this round's leader report feeds into the next round's pre-election negotiations).

- **Reflection phase** (already exists at `engine.py:1390-1431`): Still fires after post-harvest interaction. Each agent produces free-text reflection + plan.

### Intent

The two free_interaction phases have fundamentally different information and purpose. Pre-election: uncertainty, coalition-building, no winner. Post-election + post-harvest: concrete outcomes, accountability, known leader track record. Separating them explicitly in the code (not just both labeled "discussion") makes the engine's behavior clearer and lets prompts reference the right context.

## 6. Channels

### Design

- Channels form during free_interaction phases (both pre- and post-harvest)
- Used to plan, lobby, and negotiate the upcoming phase
- **Dissolve at end of the phase** — every channel auto-clears when the phase transitions
- **Empty channels (no members) auto-dissolve immediately** (existing behavior, `channels.py:251-265`)
- Personal logs persist across phases (memory of deals survives)
- Resources persist across rounds (transfers survive, are not reset)

### Motivation

The user said: *"private groupchat that get formed per phase to discuss next phase."* Channels are meeting rooms for the upcoming phase, not long-term alliances. The current design (`engine.py:287-301`, `_reset_round_state`) does NOT clear channels between phases — channels persist across the entire round, meaning agents can form a group in pre-election and stay in it through harvest. This is wrong.

### Intent

Per-phase dissolution forces repeated coalition-formation. An agent who colluded with Kate in pre-election can't just stay in the same channel for harvest — the channel dissolves, and they must actively regroup if they want to continue cooperating. This creates more LLM calls, more negotiation overhead, and more opportunities for strategic realignment. It prevents "set it and forget it" coalitions and keeps the simulation dynamic.

### Implementation

The dissolution fires at the **END** of the previous phase (before transitioning to the next phase), not at the start of the next phase:

1. **End of pre-election free_interaction** → dissolve all private channels before election phase starts
2. **End of election phase** → dissolve any channels (shouldn't be any, but safety check)
3. **End of harvest phase** → dissolve any channels before post-harvest interaction
4. **End of post-harvest free_interaction** → dissolve all channels before reflection phase

Practical implementation: call `_dissolve_private_channels()` at the END of each phase that could create channels (i.e., at the end of `_run_free_interaction()`). The method should iterate `ChannelManager._agent_channel`, move all agents back to "public", and delete private channel entries.

## 7. Election & Voting

### Design

- **Candidacy**: Optional. An agent pays 5 fish to run. Fish burned (sunk cost). If the agent can't pay (`resources < 5`), they can't run.
- **Pre-election lobbying**: Agents use ephemeral private channels to negotiate platforms, vote-trades, bribes, transfers for policy promises.
- **Campaign phase**: Each candidate publicly states their proposed `harvest_limit`, `penalty_rate`, and a free-text message.
- **Voting**: Secret ballot. Only totals public. Individual votes are invisible to other agents (not recorded in any prompt context, not in personal logs for anyone except the voter).
- **Leader's power**: Set `harvest_limit` + `penalty_rate` for the round.
- **Elections fire every round** (including round 1).

### Motivation

The user said: *"the leader is supposed to be able to set harvest limit and penalty rate, this would encourage people to pay politician for better policy, or that's the idea."* The leader's power IS the leader's currency — it creates an implicit market for policy influence. Without elective cost, everyone runs and the leader is just a random assignment. Without secret ballot, vote-monitoring eliminates side-deals ("you promised to vote for me but I'll know if you didn't" kills the trust/defection dynamic).

### Intent

- **5-fish cost** (new feature): Creates a real participation decision. An agent with 20 fish spends 25% of their wealth to run. This means only agents who believe they can win (or who are bribed to run as a spoiler) will enter. Fewer candidates = more strategic voting.
- **Secret ballot**: Enables vote-buying ("I'll give you 3 fish to vote for Emma") without enforcement. The buyer can't verify compliance. This creates trust dynamics — do I pay upfront? Do I renege? It mirrors real political corruption.
- **Elections every round**: Keeps pressure on. A leader who sets a harsh penalty rate may lose the next election. A leader who sets a lenient rate may cause pool collapse. Each round is a referendum.
- **Policy-setting**: The newly elected leader's platform becomes policy immediately. There's no "previous leader's policy carries over" — `_reset_round_state()` at `engine.py:287` already clears `self.leader_limit` and `self.leader_penalty_rate` at round start. This is correct behavior (keep, no change needed).

### Implementation changes

- **Current (`engine.py:949-950`)**: `candidates = list(self.agent_list)` (all agents). Change to filter only agents who choose to pay 5 fish.
- **Candidacy cost deduction**: Before running, deduct 5 fish from the agent. If `agent.resources < 5`, skip them. The cost is burned (sunk), not transferred.
- **Recording**: `recorder.py` already records `record_vote` with voter and candidate IDs. The `voter_map` in the election result is for the recorder/output only, NOT injected into agent prompts.
- **Vote exclusion from prompts**: `_build_vote_context` should NOT include previous votes. `_format_log_entry` for type "vote" is already for the voter's personal log only — correct behavior.

#### Edge Cases

- **No candidates run** (all agents skip candidacy or have < 5 fish): Fall back to the configured `default_limit` and `default_penalty_rate` (10.0 and 0.5 per the drama config). No leader is elected. The harvest phase uses the default policy. This is a realistic failure mode — sometimes nobody wants to lead. It creates a "leaderless round" with default rules.
- **All agents have < 5 fish**: Same as above. No one can afford to run. Default policy applies. This is more likely in late rounds when resources are depleted — an emergent consequence of the cost model.
- **Agent tries to run but can't afford candidacy cost**: The `nominate` action silently fails and the agent falls back to `pass`. No error, no crash — the agent becomes a voter only.

## 8. Visibility Rules

| Info | Visible to whom |
|---|---|
| Each agent's harvest (amount caught) | All agents |
| Total fish left (pool) | All agents |
| Public channel messages | All agents |
| Private channel messages | Only channel members |
| Public transfers (sender in public channel) | All agents |
| Private transfers (sender in private channel) | Only channel members |
| Campaign platforms (harvest_limit, penalty_rate, message) | All agents |
| Vote totals (candidate: vote count) | All agents |
| Individual votes (who voted for whom) | Nobody except the voter |
| Candidacy payments (5 fish burned, who ran) | All agents |
| Penalties imposed (who got fined, amount, reason) | All agents |
| Personal logs | Only the owning agent |
| Leader's identity + policy (limit, penalty rate) | All agents |

### Motivation

The user said: *"transfer is only visible for channel members."* The channel is a complete private bubble — both talk and resource transfers within it are invisible to outsiders. This is already partially implemented: `_execute_transfer` (`engine.py:659-692`) doesn't broadcast to non-members, but there's no check on whether the transfer occurred in a private or public context. Since agents can only talk in their current channel, a transfer made while in a private channel should be invisible to non-members.

### Intent

- **Private transfers invisible**: Enables secret vote-buying and bribery. Kate can give Luke 3 fish in their private channel, and Jack (in the public channel) sees nothing. This makes coalition-formation genuinely opaque.
- **Systemic transparency**: Who ran, who won, who got fined — all public. Agents need this information to make decisions and build reputations. Kate can't hide the fact that she was penalized; Jack can use this when deciding whether to trust her.
- **Harvest amounts public**: Creates accountability. If Luke catches 18 fish (exceeding the 10 limit), everyone knows. This enables social enforcement (even if the leader doesn't penalize, other agents can sanction socially).
- **Individual votes secret**: Prevents verification of vote-buying deals. Kate promises Emma "I'll vote for you if you give me 2 fish" — but Emma can't verify Kate actually voted for her. This creates the classic trust problem that makes corruption interesting.

## 9. Reflection & Memory

### Design

- **Reflection phase** fires at end of each round (after post-harvest free interaction, before `_reset_round_state`)
- Each agent makes an LLM call to produce free-text output:
  - **Reflection**: What just happened, what I learned, how I feel about it
  - **Plan**: What I intend to do next round
- Output stored in `agent.memories` (type `"reflection"`)
- Injected into next round's prompt under heading **"YOUR REFLECTIONS FROM LAST ROUND"**

### What is excluded from the agent's prompt

- **Conversation analysis labels** (significance tags like "collusion", "betrayal", "deal"): These are for the visualizer only. The `_analyze_conversation()` method at `engine.py:1433` writes to `self._analysis_results` which feeds the recorder output. The agent should NOT see these labels — they represent an omniscient third-party analysis, not the agent's subjective experience.
- **Last round LLM-generated summary** (the omniscient round summary at `engine.py:1275-1324`): The agent's own reflection replaces this. The agent should summarize what it experienced in its own words, not read a god-view summary.

### What IS injected

1. **MY REFLECTIONS FROM LAST ROUND**: The agent's own reflection + plan text (free-text, subjective, first-person-adjacent)
2. **Personal log (last 1 round)**: Every turn the agent witnessed, formatted chronologically
3. **Current round state**: Real-time visibility, always included

### Motivation

The user said: *"we don't need last round summary as agent is supposed to summarize what they experience in the round subjectively as reflection. the labels also is just for the visualization, the agent don't need to see that."*

### Intent

- **Subjective voice**: Each agent has personality-shaped memory written in its own word. This preserves individual perspective and avoids homogenized behavior (all agents reading the same omniscient summary think alike).
- **No god-view**: The agent only knows what it personally saw, heard, and experienced. This makes the information asymmetry created by private channels meaningful — two agents who were in different channels have genuinely different information.
- **Reflection replaces summary**: The old `round_summary` memory type (`agent.py:27`, `engine.py:1318`) can be deprecated. Reflections (`type="reflection"`) become the primary memory mechanism. The round summary LLM call at `engine.py:1326-1329` can be either removed or retained for the recorder output (the visualizer may want it).

## 10. Prompt Context Block

### New Structure

For every decision prompt, the agent receives:

1. **Identity & personality** (paragraph, with role reminder)
2. **Current game state** (round, phase, fish, leader, policy, pool status)
3. **MY REFLECTIONS** (agent's free-text reflection + plan from last round)
4. **Personal log (last 1 round)** — every turn the agent witnessed
5. **Other agents' state** — current fish (from engine state, this is public info); last action observed (from personal log)
6. **Channel/invite status** — current channel, members, pending invites
7. **Available actions + format** (dyanmic per phase)

### What is excluded

| Old field | Why excluded |
|---|---|
| Last round (LLM) summary | Agent's own reflection replaces this |
| Conversation analysis labels | Visualizer-only, gives god-view |
| Previous round personal log (full) | Limited to 1 round back to fit context |

### Motivation

The original design proposal included a "KEY EVENTS" section with analysis labels and an "OMNISCIENT SUMMARY" section. The user correctly rejected both. The agent should not receive third-party analysis of its own conversations — that's meta-gaming. And the agent should not receive a god-view summary — its own reflection serves that purpose with subjective perspective.

### Intent

The prompt context block provides the agent with everything it needs and nothing it doesn't. It has:
- **Identity** to ground its role
- **Current state** for situational awareness
- **Subjective memory** (its own reflections + personal log) for continuity
- **Channel status** to know who it can talk to
- **Available actions** so it knows what's possible

This design keeps prompts self-contained (no external state needed) and prevents information leakage from private channels.

### Implementation

The `_build_memory_context()` method at `engine.py:824-943` already builds most of this. Required changes:
1. Remove `round_summary` injection (`engine.py:927-933`)
2. Remove `_analysis_results` from prompt context (it was never wired in, but `engine.py:1433` comment says "feed into next round's prompts" — change that comment)
3. Collapse reflection window to last 1 round (currently `[-2:]` at line 939)
4. Add campaign/vote/harvest prompts full context block (currently they're minimal — `build_campaign_prompt` at `prompts.py:96-124` has no state info, `build_vote_prompt` at `prompts.py:127-152` has no agent state)

## 11. Bug Fixes

All 18 bugs from the review, with file:line references:

| # | Bug | File:Line | Fix |
|---|---|---|---|
| 1 | `group` field not parsed by DeepSeek client | `llm_client.py:119-137` | Add `data.get("group")` to `LLMResponse` |
| 2 | `_execute_talk()` and `_execute_talk_channel()` are no-op stubs | `engine.py:447-483` | Delete both; wire talk routing through channel system directly |
| 3 | No `fish` action dispatch in free interaction | `engine.py:353-369` | Add `elif normalized == "fish":` handler |
| 4 | Harvest phase ignores `action` field | `engine.py:1091-1094` | Harvest prompt asks for a number (amount to fish), not an action. If 0 or missing, skip harvest. Prompt builder is phase-aware. |
| 5 | Transfer with null target silently fails | `engine.py:659-664` | Record explicit failure in personal log |
| 6 | Dead `Action`/`ActionType` enum | `actions.py:15-47` | **Delete** the `Action` dataclass and `ActionType` enum (unused by engine; engine uses raw strings on `LLMResponse` and `_ACTION_ALIASES` dict) |
| 7 | `_analyze_conversation()` results not wired | `engine.py:1433` | Results go to recorder only (not agent prompt) — fix comment |
| 8 | Dead `Agent.relationships` state | `agent.py:14-19, 48` | Remove or keep as placeholder for future trust modeling |
| 9 | Channels persist across phases, not dissolved per-phase | `engine.py:287-301` | Add `_dissolve_private_channels()` called at phase transitions |
| 10 | Greedy JSON regex `r'\{.*\}'` | `llm_client.py:38` | Replace with non-greedy `r'\{.*?\}'` or robust parser |
| 11 | `default_penalty_rate: 0.0` | `config.py:31` | Change to `0.5` (new default config, keep old for sandbox) |
| 12 | Candidacy is forced, no cost | `engine.py:949-950` | Make optional with 5-fish sunk cost |
| 13 | `first_election_round: 2` | `config.py:35` | **Replace** with `elections_every_round: true` flag (elections fire every round including round 1) |
| 14 | New leader's policy resets each round | `engine.py:287` (existing) | **Keep** — correct behavior, no change |
| 15 | Harvest prompt lacks full context | `prompts.py:155-193` | Inject `build_memory_context()` like decision prompt |
| 16 | Campaign prompt lacks full context | `prompts.py:96-124` | Inject player state, memory, reflections |
| 17 | Vote prompt lacks full context | `prompts.py:127-152` | Inject player state, memory, relationship to candidates |
| 18 | Pool collapse threshold `== 0` | `engine.py:237` | Change to `< 0.01` (float safety) |

## 12. New Features

1. **Per-phase channel auto-dissolution**: All private channels dissolved when moving between phases. Agents return to "public". Requires a new `ChannelManager.dissolve_all()` method and calls at each phase boundary in `engine.py`.

2. **Pre-election lobbying workflow**: The pre-election free_interaction phase is explicitly for coalition-building. Agents form channels, negotiate platforms, transfer fish for vote promises, and set up the election.

3. **Secret ballot**: Vote totals are public (`recorder.py:161-175` records `vote_counts` and `voter_map` for output). Individual votes are visible ONLY to the voter (in personal log) and the recorder output (for the visualizer). NOT visible to other agents' prompts.

4. **Reflection phase with reflection + plan** (verified): The code at `engine.py:1390-1431` already exists and is correct. Output is stored as `"reflection"` type memories and injected into the next round's prompt. Plan is embedded in the reflection text (not a separate field). No new code needed — just ensure the phase runs and that the prompt context (Section 10) correctly injects reflections.

5. **Per-agent candidacy with fish cost**: Optional. Pay 5 fish to run. If resources < 5, cannot run. Sunk cost (burned, not transferred). Agents who don't run are voters only.

6. **Full prompt context block**: Campaign, vote, and harvest prompts get the same memory context as decision prompts (identity, state, reflections, personal log, channel status).

7. **Conversation analysis feed to visualizer**: `_analyze_conversation()` at `engine.py:1433` writes to `_analysis_results`. This survives into the recorder output (`recorder.py:231-232`). The visualizer uses it for collusion detection panel. The agent prompt does NOT see these labels.

8. **Memory window: 1 round**: Personal log window reduced from 2 rounds to 1 round (`engine.py:891`). This keeps prompt size manageable and forces agents to rely on their reflections for older events.

## 13. Test & Observability

### Recorder extensions

- Add `channel_states` snapshot to recorder output: at each recorded event, include the current state of all channels (who's in which channel). This lets the visualizer reconstruct channel membership without walking the turn sequence.
- Include `personal_log` in recorder output: per-agent, full log. Currently `recorder.py:205-207` only stores `agent_memories` (the high-level Memory objects), not the detailed `personal_log`. Adding `personal_log` to the output enables the visualizer and makes debugging easier.

### Test fixes

- **`test_private_talk_excluded_from_third_party`**: Currently tests itself (tautological assertion). Fix to actually verify that a non-member agent's personal log doesn't contain private channel messages.
- **`test_violator_gets_penalty_entry`**: Currently `assert True`. Implement real assertion checking that an agent who exceeds the limit has a penalty entry in their personal log.
- **`test_leader_persists_when_no_new_election`**: Currently `pass`. Test that leader carries over when `first_election_round > current_round` (only relevant for sandbox config with first_election_round > 1).

### New tests

- **`heard_by` validation**: Verify that private channel messages have the correct `heard_by` set (only channel members).
- **Transfer null target**: Verify that a transfer with `target = None` records a failure in the sender's personal log.
- **Group field fix**: Verify that `LLMResponse.group` is correctly parsed from the LLM response.
- **Per-phase channel dissolution**: Verify that after a phase transition, all agents are in "public" and private channels are deleted.
- **Reflection phase output**: Verify that after reflection, each agent has at least one `"reflection"` type Memory with non-empty content.
- **Candidacy cost**: Verify that running for leader deducts 5 fish, and agents with `< 5` resources cannot run.

### Motivation

The current test suite has several `pass` and `assert True` placeholders that were never implemented. The recorder output lacks channel state snapshots and personal logs, making debugging and visualizer work harder. These fixes close the gap between "the sim runs" and "the sim is correctly observable and testable."

## 14. Migration

### Config mapping

The old `config/five_agents.yaml` (4 agents: Kate, Jack, Emma, Luke; 2 rounds; penalty=0.0) is retained as a **"ceremonial/sandbox" preset** for basic testing and visualizer development. It does NOT use the new mechanics (no candidacy cost, no secret ballot enforcement, penalty rate 0.0).

A new `config/five_agents_drama.yaml` becomes the **recommended default**:

| Field | `five_agents.yaml` (old/sandbox) | `five_agents_drama.yaml` (new/default) |
|---|---|---|
| Agents | Kate, Jack, Emma, Luke (4) | John, Kate, Jack, Emma, Luke (5) |
| Rounds | 2 | 3 |
| Turns/phase | 4 | 10 |
| Starting fish | 50.0 | 20.0 |
| Pool capacity | 100 | 100 |
| Regen factor | 1.5 | 2.0 |
| Fish/harvest | 5.0 | 10.0 |
| Penalty rate | 0.0 | 0.5 |
| First election | Round 2 | Every round (config flag) |
| Candidacy cost | n/a (all agents forced) | 5 fish (optional) |

### Other configs

- **`collapse_test.yaml`** (2 agents, 10 rounds, pool=20, regen=0.5, fish=15): Needs `first_election_round` removed (use `elections_every_round: true` instead) and candidacy cost added. **Note:** With only 2 agents and a 5-fish cost (25% of 20 starting resources), both agents may skip candidacy. Either: (a) lower candidacy cost to 2 fish for this config, or (b) add a `candidacy_cost: 2.0` override to `collapse_test.yaml`, or (c) redesign the test to accept that elections may have 0 candidates (fall back to defaults). Recommend (b) for simplicity.
- **`invite_test.yaml`** (2 agents, 1 round, personality-driven): Needs candidacy cost added. Currently `first_election_round: 2` which means the election never fires in a 1-round test. With `elections_every_round: true`, it will fire in round 1. Test may need personality updates to handle candidacy.

### Output compatibility

Existing test outputs in `outputs/` are stale (generated with old mechanics). They can be kept for reference but should not be used as test fixtures for v2. New test runs should regenerate output files.

## 15. Open Questions — Resolved

1. **Post-collapse behavior** — **Resolved**: Game ends immediately on pool collapse. No debrief round. The `engine.py:237-242` break fires and the simulation stops. Clean break.

2. **Reflection content and voting record** — **Resolved**: The agent's own vote is included in the reflection prompt. The agent knows how it voted, so this enables self-reflection about voting decisions. The reflection prompt should include: "How did you vote this round?" and "Did your vote align with your plans?"

3. **`Agent.relationships` dead state** — **Resolved**: Delete. The `Relationship` dataclass (`agent.py:14-19`) and `Agent.relationships` field (`agent.py:48`) are dead code. Remove both.

4. **Candidacy cost destination** — **Resolved**: Burned, no destination. Sunk cost.

5. **LLM response `action` field in harvest phase** — **Resolved**: The harvest prompt should simply ask for a number (how many fish to take). No action field needed. The prompt builder should be flexible per phase — each phase constructs its own prompt format. For harvest: ask for a number between 0 and pool remaining. For free interaction: ask for action + details. For election: ask for platform + vote. The prompt builder function should take a phase parameter and return the appropriate prompt structure. If the LLM returns 0 or the field is missing, the agent skips harvesting.
