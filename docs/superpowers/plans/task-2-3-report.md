# Task 2 & Task 3 Report — End-condition fields in recorder + collapse test

## Summary

Task 2: Added `end_condition`, `collapsed_at_round`, and `survival_length` fields to the Recorder, with a `set_end_condition()` setter and engine wiring to propagate collapse state from the Engine's existing fields. Implemented TDD: wrote failing tests first, then implemented, then verified all pass.

Task 3: Created `config/collapse_test.yaml` (low capacity, aggressive fish amounts), ran collapse simulation in stub mode confirming pool collapse at round 1, verified output JSON contains correct end_condition fields. Ran normal config (`five_agents.yaml`) in stub mode confirming `end_condition: "time_limit"` output. Full test suite passes with 252/252.

## Files Changed

- `simulation/recorder.py` — Added `_end_condition`, `_collapsed_at_round`, `_survival_length` fields in `__init__`; added `set_end_condition()` setter; added three fields to `get_output()` dict
- `simulation/engine.py` — Added recorder end-condition population call in `run()` before `_set_recorder_metadata()`
- `tests/test_engine_collapse.py` — Added `TestRecorderEndCondition` class with 3 tests (default field presence, collapse output, time_limit output)
- `config/collapse_test.yaml` — New collapse-oriented config (capacity=20, regen=0.5, fish=15, 2 agents)

## Test Results

All 252 tests pass:
```
python -m pytest -q  →  252 passed in 1.65s
```

Specific new tests:
```
python -m pytest tests/test_engine_collapse.py::TestRecorderEndCondition -v
  ✓ test_recorder_get_output_has_end_condition
  ✓ test_end_condition_collapse_in_output
  ✓ test_end_condition_time_limit
```

## Collapse Output Verification

**Collapse run** (`config/collapse_test.yaml`, stub mode):
- `end_condition`: "collapse"
- `collapsed_at_round`: 1
- `survival_length`: 1
- Only 1 round (early termination)
- Output: `outputs/collapse_test_output.json`

**Normal run** (`config/five_agents.yaml`, stub mode):
- `end_condition`: "time_limit"
- `collapsed_at_round`: None
- `survival_length`: 2
- Both rounds completed normally
- Output: `outputs/normal_test_output.json`

## Commit History

```
5679d56 feat: add end_condition fields to recorder + collapse test config
e04b6b9 feat: add pool-collapse end condition to engine
```

## Concerns

- The ⚠ Unicode character in `engine.py` line 241 causes a `UnicodeEncodeError` on Windows in CP1252 terminals. This is pre-existing (introduced in Task 1) and only affects the verbose console output; the JSON output is correct. Workaround: set `$env:PYTHONIOENCODING='utf-8'` before running.
- `git add -A` failed due to a rogue `nul` file in the repo root (probably leftover from a Windows filesystem operation). Staged specific files instead.
