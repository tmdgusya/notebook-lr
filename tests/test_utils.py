"""
Tests for format_output() and format_rich_output() in utils.py.

Most tests in TestFormatOutput are EXPECTED TO FAIL with current code because
format_output() only reads text/plain, ignoring text/html and other MIME types.
"""

import importlib.util
import json
import sys
from pathlib import Path
import pytest

# Import utils directly to avoid __init__.py pulling in session.py (needs dill)
_utils_path = Path(__file__).parent.parent / "notebook_lr" / "utils.py"
_spec = importlib.util.spec_from_file_location("notebook_lr.utils", _utils_path)
_utils = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_utils)
format_output = _utils.format_output
format_rich_output = _utils.format_rich_output


class TestFormatOutput:
    """Tests for format_output() MIME type handling."""

    # --- Tests expected to FAIL with current code ---

    def test_execute_result_with_html_returns_html(self):
        """When both text/html and text/plain exist, HTML should be returned."""
        output = {
            "type": "execute_result",
            "data": {
                "text/html": "<h1>Hi</h1>",
                "text/plain": "fallback",
            },
        }
        result = format_output(output)
        assert result == "<h1>Hi</h1>", (
            f"Expected HTML content but got: {result!r}"
        )

    def test_execute_result_html_only(self):
        """Output with only text/html should return the HTML content."""
        output = {
            "type": "execute_result",
            "data": {
                "text/html": "<table><tr><td>data</td></tr></table>",
            },
        }
        result = format_output(output)
        assert result == "<table><tr><td>data</td></tr></table>", (
            f"Expected HTML content but got: {result!r}"
        )

    def test_display_data_with_html(self):
        """display_data type with text/html should return HTML content."""
        output = {
            "type": "display_data",
            "data": {
                "text/html": "<div class='plot'>chart</div>",
                "text/plain": "chart",
            },
        }
        result = format_output(output)
        assert result == "<div class='plot'>chart</div>", (
            f"Expected HTML content but got: {result!r}"
        )

    def test_execute_result_with_markdown(self):
        """Output with text/markdown should return the markdown content."""
        output = {
            "type": "execute_result",
            "data": {
                "text/markdown": "# Heading\n\nSome **bold** text",
                "text/plain": "Heading\n\nSome bold text",
            },
        }
        result = format_output(output)
        assert result == "# Heading\n\nSome **bold** text", (
            f"Expected markdown content but got: {result!r}"
        )

    def test_execute_result_with_json(self):
        """Output with application/json should return a JSON string."""
        payload = {"key": "value", "number": 42}
        output = {
            "type": "execute_result",
            "data": {
                "application/json": payload,
                "text/plain": "{'key': 'value', 'number': 42}",
            },
        }
        result = format_output(output)
        # Should be a valid JSON representation of the payload
        parsed = json.loads(result)
        assert parsed == payload, (
            f"Expected JSON content but got: {result!r}"
        )

    def test_format_output_prefers_html_over_plain(self):
        """When both text/html and text/plain exist, HTML must be preferred."""
        output = {
            "type": "execute_result",
            "data": {
                "text/plain": "plain fallback",
                "text/html": "<b>rich</b>",
            },
        }
        result = format_output(output)
        assert "plain fallback" not in result, (
            "Should not return plain text when HTML is available"
        )
        assert "<b>rich</b>" in result, (
            f"Expected HTML in result but got: {result!r}"
        )

    # --- Regression tests expected to PASS with current code ---

    def test_execute_result_plain_text_still_works(self):
        """Output with only text/plain should still work correctly."""
        output = {
            "type": "execute_result",
            "data": {
                "text/plain": "42",
            },
        }
        result = format_output(output)
        assert result == "42"

    def test_stream_still_works(self):
        """Stream type outputs should still work."""
        output = {
            "type": "stream",
            "name": "stdout",
            "text": "Hello, World!\n",
        }
        result = format_output(output)
        assert result == "Hello, World!\n"

    def test_error_still_works(self):
        """Error type outputs should still work."""
        output = {
            "type": "error",
            "ename": "ZeroDivisionError",
            "evalue": "division by zero",
            "traceback": [],
        }
        result = format_output(output)
        assert "ZeroDivisionError" in result
        assert "division by zero" in result


class TestFormatRichOutput:
    """Tests for format_rich_output() MIME type handling."""

    # --- Tests expected to FAIL with current code ---

    def test_rich_execute_result_with_html(self):
        """format_rich_output should handle text/html in execute_result."""
        output = {
            "type": "execute_result",
            "data": {
                "text/html": "<h1>Hello</h1>",
                "text/plain": "Hello",
            },
        }
        result = format_rich_output(output)
        # The renderable should represent the HTML content, not just plain text
        rendered_text = str(result)
        assert "<h1>Hello</h1>" in rendered_text, (
            f"Expected HTML in rich output but got: {rendered_text!r}"
        )

    def test_rich_display_data_with_html(self):
        """format_rich_output should handle text/html in display_data."""
        output = {
            "type": "display_data",
            "data": {
                "text/html": "<p>paragraph</p>",
                "text/plain": "paragraph",
            },
        }
        result = format_rich_output(output)
        rendered_text = str(result)
        assert "<p>paragraph</p>" in rendered_text, (
            f"Expected HTML in rich output but got: {rendered_text!r}"
        )
