"""
Comprehensive tests for format_output() in notebook_lr/utils.py.
"""

import importlib.util
import json
from pathlib import Path

import pytest

# Import format_output directly to avoid __init__.py side effects
_utils_path = Path(__file__).parent.parent / "notebook_lr" / "utils.py"
_spec = importlib.util.spec_from_file_location("notebook_lr.utils", _utils_path)
_utils = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_utils)
format_output = _utils.format_output


class TestFormatOutputStream:
    """Tests for stream output type."""

    def test_stream_stdout_returns_text(self):
        """1. type='stream', name='stdout' returns text."""
        output = {"type": "stream", "name": "stdout", "text": "hello\n"}
        assert format_output(output) == "hello\n"

    def test_stream_stderr_returns_text(self):
        """2. type='stream', name='stderr' returns text."""
        output = {"type": "stream", "name": "stderr", "text": "error output\n"}
        assert format_output(output) == "error output\n"

    def test_stream_empty_text_returns_empty_string(self):
        """3. type='stream' with empty text returns ''."""
        output = {"type": "stream", "name": "stdout", "text": ""}
        assert format_output(output) == ""

    def test_stream_missing_text_key_returns_empty_string(self):
        """4. type='stream' with missing 'text' key returns ''."""
        output = {"type": "stream", "name": "stdout"}
        assert format_output(output) == ""


class TestFormatOutputExecuteResult:
    """Tests for execute_result output type."""

    def test_execute_result_with_html_returns_html(self):
        """5. execute_result with text/html returns HTML."""
        output = {
            "type": "execute_result",
            "data": {"text/html": "<b>bold</b>", "text/plain": "bold"},
        }
        assert format_output(output) == "<b>bold</b>"

    def test_execute_result_with_markdown_returns_markdown(self):
        """6. execute_result with text/markdown returns markdown."""
        output = {
            "type": "execute_result",
            "data": {"text/markdown": "# Heading", "text/plain": "Heading"},
        }
        assert format_output(output) == "# Heading"

    def test_execute_result_with_json_dict_returns_formatted_json(self):
        """7. execute_result with application/json (dict) returns formatted JSON."""
        payload = {"key": "value", "number": 42}
        output = {
            "type": "execute_result",
            "data": {"application/json": payload},
        }
        result = format_output(output)
        parsed = json.loads(result)
        assert parsed == payload
        assert result == json.dumps(payload, indent=2)

    def test_execute_result_with_json_string_returns_as_is(self):
        """8. execute_result with application/json (string) returns as-is."""
        output = {
            "type": "execute_result",
            "data": {"application/json": "already a string"},
        }
        assert format_output(output) == "already a string"

    def test_execute_result_with_only_plain_text_returns_plain(self):
        """9. execute_result with only text/plain returns plain text."""
        output = {
            "type": "execute_result",
            "data": {"text/plain": "42"},
        }
        assert format_output(output) == "42"

    def test_execute_result_with_empty_data_returns_empty_string(self):
        """10. execute_result with empty data dict returns ''."""
        output = {"type": "execute_result", "data": {}}
        assert format_output(output) == ""

    def test_execute_result_prefers_html_over_plain(self):
        """11. execute_result prefers text/html over text/plain."""
        output = {
            "type": "execute_result",
            "data": {
                "text/plain": "plain fallback",
                "text/html": "<b>rich</b>",
            },
        }
        result = format_output(output)
        assert result == "<b>rich</b>"
        assert "plain fallback" not in result


class TestFormatOutputError:
    """Tests for error output type."""

    def test_error_with_ename_and_evalue(self):
        """12. type='error' with ename and evalue returns 'ename: evalue'."""
        output = {
            "type": "error",
            "ename": "ValueError",
            "evalue": "invalid value",
        }
        assert format_output(output) == "ValueError: invalid value"

    def test_error_with_empty_evalue(self):
        """13. type='error' with empty evalue returns 'ename: '."""
        output = {
            "type": "error",
            "ename": "StopIteration",
            "evalue": "",
        }
        assert format_output(output) == "StopIteration: "

    def test_error_with_missing_ename_defaults_to_error(self):
        """14. type='error' with missing ename defaults to 'Error'."""
        output = {
            "type": "error",
            "evalue": "something went wrong",
        }
        result = format_output(output)
        assert result == "Error: something went wrong"


class TestFormatOutputDisplayData:
    """Tests for display_data output type."""

    def test_display_data_with_html_returns_html(self):
        """15. display_data with text/html returns HTML."""
        output = {
            "type": "display_data",
            "data": {"text/html": "<div>chart</div>", "text/plain": "chart"},
        }
        assert format_output(output) == "<div>chart</div>"

    def test_display_data_with_markdown_returns_markdown(self):
        """16. display_data with text/markdown returns markdown."""
        output = {
            "type": "display_data",
            "data": {"text/markdown": "## Section", "text/plain": "Section"},
        }
        assert format_output(output) == "## Section"

    def test_display_data_with_json_returns_formatted_json(self):
        """17. display_data with application/json returns formatted JSON."""
        payload = {"plot": "data"}
        output = {
            "type": "display_data",
            "data": {"application/json": payload},
        }
        result = format_output(output)
        parsed = json.loads(result)
        assert parsed == payload

    def test_display_data_with_only_plain_text_returns_it(self):
        """18. display_data with only text/plain returns it."""
        output = {
            "type": "display_data",
            "data": {"text/plain": "hello"},
        }
        assert format_output(output) == "hello"

    def test_display_data_with_empty_data_returns_str_data(self):
        """19. display_data with empty data returns str(data)."""
        output = {"type": "display_data", "data": {}}
        assert format_output(output) == str({})


class TestFormatOutputEdgeCases:
    """Tests for edge cases."""

    def test_unknown_output_type_returns_str_output(self):
        """20. Unknown output type returns str(output)."""
        output = {"type": "unknown_type", "data": "something"}
        assert format_output(output) == str(output)

    def test_empty_dict_returns_str_empty_dict(self):
        """21. Empty dict returns str({})."""
        output = {}
        assert format_output(output) == str({})

    def test_missing_type_key_returns_str_output(self):
        """22. Missing 'type' key returns str(output)."""
        output = {"data": {"text/plain": "hello"}}
        assert format_output(output) == str(output)
