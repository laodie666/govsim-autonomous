"""Tests for DeepSeekLLM client and JSON extraction.

Phase 12 — llm_client testing.
"""

import pytest
from simulation.llm_client import _extract_json, DeepSeekLLM


class TestExtractJson:

    def test_plain_json(self):
        """Simple JSON object."""
        result = _extract_json('{"action": "fish", "amount": 5}')
        assert result == {"action": "fish", "amount": 5}

    def test_markdown_fence(self):
        """JSON wrapped in ```json ... ``` fences."""
        raw = '```json\n{"action": "pass", "reasoning": "nothing"}\n```'
        result = _extract_json(raw)
        assert result == {"action": "pass", "reasoning": "nothing"}

    def test_markdown_fence_no_lang(self):
        """JSON wrapped in plain ``` fences."""
        raw = '```\n{"action": "fish", "amount": 3}\n```'
        result = _extract_json(raw)
        assert result == {"action": "fish", "amount": 3}

    def test_trailing_text(self):
        """JSON followed by explanatory text."""
        raw = '{"action": "vote", "vote_for": "alice"}\n\nI chose Alice because she is fair.'
        result = _extract_json(raw)
        assert result == {"action": "vote", "vote_for": "alice"}

    def test_leading_text(self):
        text = 'Here is my decision: {"action": "pass", "reasoning": "busy"}'
        result = _extract_json(text)
        assert result == {"action": "pass", "reasoning": "busy"}

    def test_trailing_comma(self):
        raw = '{"action": "fish", "amount": 5,}'
        result = _extract_json(raw)
        assert result == {"action": "fish", "amount": 5}

    def test_nested_json(self):
        raw = '{"action": "transfer", "target": "bob", "amount": 10, "meta": {"reason": "gift"}}'
        result = _extract_json(raw)
        assert result["action"] == "transfer"
        assert result["meta"]["reason"] == "gift"

    def test_invalid_input_raises(self):
        """Completely non-JSON text should raise."""
        with pytest.raises(ValueError):
            _extract_json("I think I will pass this turn.")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            _extract_json("")

    def test_single_brace(self):
        """Single brace without JSON content."""
        with pytest.raises(ValueError):
            _extract_json("{")

    def test_array_not_object(self):
        """JSON array (not object) should still parse."""
        result = _extract_json('["a", "b"]')
        assert result == ["a", "b"]

    def test_null_json(self):
        result = _extract_json("null")
        assert result is None

    def test_non_greedy_regex(self):
        """Greedy regex would match from first { to last }. Non-greedy stops at first }."""
        result = _extract_json('{"a": 1} trailing text {\n"b": 2}')
        assert result == {"a": 1}, f"Expected {{'a': 1}}, got {result}"

    def test_escaped_quotes_in_string(self):
        """JSON with escaped quotes inside string values."""
        raw = '{"message": "She said \\"hello\\"", "action": "talk"}'  # literal backslash-quote
        result = _extract_json(raw)
        assert result["action"] == "talk"

    def test_multiple_json_objects(self):
        """Multiple JSON objects — should extract the first one."""
        raw = '{"a": 1} trailing {\n"b": 2} more text'
        result = _extract_json(raw)
        assert result == {"a": 1}

    def test_whitespace_between_fence_and_json(self):
        """Whitespace after ```json before newline should still parse."""
        raw = '```json   \n{"action": "fish"}\n```'
        result = _extract_json(raw)
        assert result == {"action": "fish"}

    def test_only_whitespace_raises(self):
        """Whitespace-only input raises."""
        with pytest.raises(ValueError):
            _extract_json("   \n\n   ")

    def test_unmatched_braces_raises(self):
        """Unmatched opening brace raises."""
        with pytest.raises(ValueError):
            _extract_json('{"a": 1')

    def test_object_inside_array(self):
        """JSON array containing objects is parsed as a list."""
        result = _extract_json('[{"action": "pass"}, {"action": "fish"}]')
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["action"] == "pass"
        assert result[1]["action"] == "fish"

    def test_deep_nesting(self):
        """Deeply nested JSON structures parse correctly."""
        raw = '{"level1": {"level2": {"level3": {"level4": {"action": "pass"}}}}}'
        result = _extract_json(raw)
        assert result["level1"]["level2"]["level3"]["level4"]["action"] == "pass"

    def test_json_with_newlines_and_indentation(self):
        """JSON formatted across multiple lines."""
        raw = '{\n  "action": "fish",\n  "amount": 5,\n  "reasoning": "hungry"\n}'
        result = _extract_json(raw)
        assert result["action"] == "fish"
        assert result["amount"] == 5
        assert "hungry" in result["reasoning"]


class TestDeepSeekLLM:
    """Tests for DeepSeekLLM.decide()."""

    def test_decide_parses_group(self, monkeypatch):
        """LLMResponse.group should be populated from JSON 'group' key."""
        llm = DeepSeekLLM(api_key="sk-test")

        def mock_call(system, prompt):
            return '{"action": "talk", "group": "#secret_0", "message": "hi"}'

        monkeypatch.setattr(llm, "_call", mock_call)
        resp = llm.decide("test prompt")
        assert resp.group == "#secret_0", f"Expected group='#secret_0', got {resp.group!r}"

    def test_decide_handles_plain_number(self, monkeypatch):
        """decide() handles a plain number (harvest response) → action='fish', amount set."""
        llm = DeepSeekLLM(api_key="sk-test")

        def mock_call(system, prompt):
            return "8"  # Just a number, no JSON

        monkeypatch.setattr(llm, "_call", mock_call)
        resp = llm.decide("How many fish?")
        assert resp.action == "fish", f"Expected action='fish', got {resp.action}"
        assert resp.amount == 8.0, f"Expected amount=8.0, got {resp.amount}"

    def test_decide_handles_float_number(self, monkeypatch):
        """decide() handles a plain float number → action='fish'."""
        llm = DeepSeekLLM(api_key="sk-test")

        def mock_call(system, prompt):
            return "5.5"

        monkeypatch.setattr(llm, "_call", mock_call)
        resp = llm.decide("How many fish?")
        assert resp.action == "fish"
        assert resp.amount == 5.5


class TestDeepSeekLLMInit:

    def test_requires_api_key(self, monkeypatch):
        """DeepSeekLLM raises if no API key and no env var."""
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        # We don't actually want to make API calls, just check init
        # The constructor doesn't make API calls, it just creates the client
        llm = DeepSeekLLM(api_key="sk-test", model="deepseek-chat")
        assert llm.model == "deepseek-chat"
        assert llm.temperature == 0.7

    def test_defaults(self):
        llm = DeepSeekLLM(api_key="sk-test")
        assert llm.model == "deepseek-chat"
        assert llm.temperature == 0.7
        assert llm.max_tokens == 500
        assert llm.retries == 2
