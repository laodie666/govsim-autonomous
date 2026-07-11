# Task 1 Report: Pool-Collapse Detection

## Status: DONE

## Commits
- `bb18402` — chore: initial commit (pre-collapse-fix baseline)
- `e04b6b9` — feat: add pool-collapse end condition to engine

## Changes

### `simulation/engine.py`
1. **`__init__`**: Added three new instance fields after line 80:
   - `self.collapsed: bool = False` — whether the pool collapsed
   - `self.collapsed_at_round: int | None = None` — round when collapse occurred
   - `self.survival_length: int = 0` — rounds survived before collapse

2. **`run()` method — collapse check**: Inserted after `_record_round_metrics()` (line 234) and before `self.pool.regenerate()` (line 244):
   - If `self.pool.amount == 0`, sets `collapsed=True`, `collapsed_at_round=round_num`, `survival_length=round_num`, prints a warning, and `break`s out of the round loop.
   - This happens BEFORE regeneration so the check catches the pool-at-zero state before the 5% regen floor kicks in.

3. **`run()` method — normal exit**: After the round loop ends (before `_set_recorder_metadata()`), if `not self.collapsed`, sets `survival_length = num_rounds`.

### `tests/test_engine_collapse.py` (new file)
- `test_engine_has_collapse_fields` — verifies `collapsed`, `collapsed_at_round`, `survival_length` exist with correct defaults
- `test_pool_collapse_ends_simulation_early` — pool hits 0 in round 1, sim stops, only 1 round recorded
- `test_no_collapse_when_pool_positive` — pool stays positive, sim runs all rounds, collapse fields remain False/None
- `test_collapse_in_later_round` — pool collapses in round 2, `collapsed_at_round == 2`
- `test_survival_length` — survival length equals the round where collapse occurred

## Test Results

| Suite | Tests | Result |
|-------|-------|--------|
| New collapse tests | 5/5 | PASS |
| Full suite (incl. new) | 249/249 | PASS (2.28s) |

No regressions.

## Concerns

None. The implementation is minimal and self-contained. The collapse check fires before regeneration, so the 5% regen floor in `resource_pool.py` does not interfere. Existing tests all pass unchanged.

## Report File
`C:\Users\laodie666\Desktop\stuff\Jinesis Lab\govsim\govsim-autonomous\docs\superpowers\plans\task-1-report.md`
