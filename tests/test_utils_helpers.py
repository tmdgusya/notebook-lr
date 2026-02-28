"""
Comprehensive tests for utility helper functions in utils.py:
- get_cell_type_icon
- get_cell_status
- is_markdown
- truncate_text
- get_timestamp
- sanitize_variable_name
- estimate_cell_lines
"""

import importlib.util
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Import utils directly to avoid __init__.py side-effects (session.py needs dill)
_utils_path = Path(__file__).parent.parent / "notebook_lr" / "utils.py"
_spec = importlib.util.spec_from_file_location("notebook_lr.utils", _utils_path)
_utils = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_utils)

get_cell_type_icon = _utils.get_cell_type_icon
get_cell_status = _utils.get_cell_status
is_markdown = _utils.is_markdown
truncate_text = _utils.truncate_text
get_timestamp = _utils.get_timestamp
sanitize_variable_name = _utils.sanitize_variable_name
estimate_cell_lines = _utils.estimate_cell_lines


# ---------------------------------------------------------------------------
# get_cell_type_icon
# ---------------------------------------------------------------------------


class TestGetCellTypeIcon:
    """Tests for get_cell_type_icon()."""

    def test_code_string_returns_py(self):
        assert get_cell_type_icon("code") == "py"

    def test_markdown_string_returns_md(self):
        assert get_cell_type_icon("markdown") == "md"

    def test_unknown_string_returns_md(self):
        # Any non-"code" value falls back to "md"
        assert get_cell_type_icon("raw") == "md"
        assert get_cell_type_icon("") == "md"
        assert get_cell_type_icon("other") == "md"

    def test_enum_like_object_with_code_value(self):
        """Objects with a .value attribute of 'code' should return 'py'."""
        mock_type = MagicMock()
        mock_type.value = "code"
        assert get_cell_type_icon(mock_type) == "py"

    def test_enum_like_object_with_markdown_value(self):
        """Objects with a .value attribute of 'markdown' should return 'md'."""
        mock_type = MagicMock()
        mock_type.value = "markdown"
        assert get_cell_type_icon(mock_type) == "md"

    def test_enum_like_object_with_other_value(self):
        mock_type = MagicMock()
        mock_type.value = "raw"
        assert get_cell_type_icon(mock_type) == "md"


# ---------------------------------------------------------------------------
# get_cell_status
# ---------------------------------------------------------------------------


def _make_cell(outputs=None, execution_count=None):
    """Create a minimal mock cell object."""
    cell = MagicMock()
    cell.outputs = outputs if outputs is not None else []
    cell.execution_count = execution_count
    return cell


class TestGetCellStatus:
    """Tests for get_cell_status()."""

    def test_no_outputs_no_execution_count_returns_pending(self):
        cell = _make_cell(outputs=[], execution_count=None)
        indicator, style = get_cell_status(cell)
        assert indicator == "--"
        assert style == "dim"

    def test_outputs_without_error_returns_ok_green(self):
        cell = _make_cell(
            outputs=[{"type": "stream", "text": "hello"}],
            execution_count=1,
        )
        indicator, style = get_cell_status(cell)
        assert indicator == "ok"
        assert style == "green"

    def test_outputs_with_error_returns_err_red(self):
        cell = _make_cell(
            outputs=[{"type": "error", "ename": "ValueError", "evalue": "bad"}],
            execution_count=1,
        )
        indicator, style = get_cell_status(cell)
        assert indicator == "err"
        assert style == "red"

    def test_outputs_mixed_stream_and_error_returns_err(self):
        """If any output is an error, status should be 'err'."""
        cell = _make_cell(
            outputs=[
                {"type": "stream", "text": "ok"},
                {"type": "error", "ename": "RuntimeError", "evalue": "oops"},
            ],
            execution_count=2,
        )
        indicator, style = get_cell_status(cell)
        assert indicator == "err"
        assert style == "red"

    def test_no_outputs_but_has_execution_count_returns_ok(self):
        """Cell executed but produced no visible output should still be 'ok'."""
        cell = _make_cell(outputs=[], execution_count=0)
        indicator, style = get_cell_status(cell)
        assert indicator == "ok"
        assert style == "green"

    def test_execute_result_output_no_error(self):
        cell = _make_cell(
            outputs=[{"type": "execute_result", "data": {"text/plain": "42"}}],
            execution_count=3,
        )
        indicator, style = get_cell_status(cell)
        assert indicator == "ok"
        assert style == "green"

    def test_multiple_stream_outputs_no_error(self):
        cell = _make_cell(
            outputs=[
                {"type": "stream", "text": "line1"},
                {"type": "stream", "text": "line2"},
            ],
            execution_count=1,
        )
        indicator, style = get_cell_status(cell)
        assert indicator == "ok"
        assert style == "green"


# ---------------------------------------------------------------------------
# is_markdown
# ---------------------------------------------------------------------------


class TestIsMarkdown:
    """Tests for is_markdown()."""

    def test_h1_header(self):
        assert is_markdown("# Title") is True

    def test_h2_header(self):
        assert is_markdown("## Section") is True

    def test_h6_header(self):
        assert is_markdown("###### Deep header") is True

    def test_bold_text(self):
        assert is_markdown("**bold text**") is True

    def test_italic_text(self):
        assert is_markdown("*italic text*") is True

    def test_link(self):
        assert is_markdown("[link text](http://example.com)") is True

    def test_code_block(self):
        assert is_markdown("```python\ncode\n```") is True

    def test_unordered_list(self):
        assert is_markdown("- item one") is True

    def test_numbered_list(self):
        assert is_markdown("1. first item") is True

    def test_plain_python_code_is_not_markdown(self):
        assert is_markdown("x = 42") is False

    def test_empty_string_is_not_markdown(self):
        assert is_markdown("") is False

    def test_plain_prose_is_not_markdown(self):
        assert is_markdown("Hello world this is plain text.") is False

    def test_multiline_with_header(self):
        text = "Some intro\n# Header here\nmore text"
        assert is_markdown(text) is True

    def test_multiline_plain_text(self):
        text = "Line one\nLine two\nLine three"
        assert is_markdown(text) is False

    def test_numbered_list_double_digit(self):
        assert is_markdown("10. tenth item") is True

    def test_header_must_have_space(self):
        # '#title' without a space after # should NOT match the header pattern
        assert is_markdown("#notaheader") is False

    def test_bold_requires_surrounding_asterisks(self):
        # Single asterisks mid-word should not trigger bold
        assert is_markdown("price*discount") is False


# ---------------------------------------------------------------------------
# truncate_text
# ---------------------------------------------------------------------------


class TestTruncateText:
    """Tests for truncate_text()."""

    def test_short_text_unchanged(self):
        assert truncate_text("hello", 100) == "hello"

    def test_exact_length_unchanged(self):
        text = "a" * 100
        assert truncate_text(text, 100) == text

    def test_longer_text_truncated_with_ellipsis(self):
        text = "a" * 110
        result = truncate_text(text, 100)
        assert len(result) == 100
        assert result.endswith("...")

    def test_default_max_length_is_100(self):
        text = "x" * 200
        result = truncate_text(text)
        assert len(result) == 100
        assert result.endswith("...")

    def test_truncated_content_is_prefix(self):
        text = "abcdefghij"
        result = truncate_text(text, 7)
        assert result == "abcd..."

    def test_empty_string(self):
        assert truncate_text("", 10) == ""

    def test_max_length_3_returns_ellipsis(self):
        """Edge case: max_length == 3 means 0 chars + '...'."""
        result = truncate_text("hello", 3)
        assert result == "..."
        assert len(result) == 3

    def test_max_length_4(self):
        result = truncate_text("hello world", 4)
        assert result == "h..."
        assert len(result) == 4


# ---------------------------------------------------------------------------
# get_timestamp
# ---------------------------------------------------------------------------


class TestGetTimestamp:
    """Tests for get_timestamp()."""

    def test_returns_string(self):
        ts = get_timestamp()
        assert isinstance(ts, str)

    def test_matches_expected_format(self):
        ts = get_timestamp()
        # Expected format: YYYY-MM-DD HH:MM:SS
        pattern = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"
        assert re.match(pattern, ts), f"Timestamp {ts!r} does not match expected format"

    def test_two_calls_are_close_in_time(self):
        """Two consecutive calls should produce timestamps within 1 second."""
        from datetime import datetime

        ts1 = get_timestamp()
        ts2 = get_timestamp()
        dt1 = datetime.strptime(ts1, "%Y-%m-%d %H:%M:%S")
        dt2 = datetime.strptime(ts2, "%Y-%m-%d %H:%M:%S")
        diff = abs((dt2 - dt1).total_seconds())
        assert diff <= 1, f"Timestamps differ by {diff}s, expected <= 1s"


# ---------------------------------------------------------------------------
# sanitize_variable_name
# ---------------------------------------------------------------------------


class TestSanitizeVariableName:
    """Tests for sanitize_variable_name()."""

    def test_valid_name_unchanged(self):
        assert sanitize_variable_name("my_var") == "my_var"

    def test_spaces_replaced_with_underscore(self):
        assert sanitize_variable_name("my var") == "my_var"

    def test_hyphens_replaced_with_underscore(self):
        assert sanitize_variable_name("my-var") == "my_var"

    def test_leading_digit_gets_underscore_prefix(self):
        result = sanitize_variable_name("1var")
        assert result.startswith("_")
        assert result == "_1var"

    def test_all_digits_gets_underscore_prefix(self):
        result = sanitize_variable_name("123")
        assert result == "_123"

    def test_special_chars_replaced(self):
        result = sanitize_variable_name("my.var!")
        assert result == "my_var_"

    def test_empty_string_returns_default(self):
        assert sanitize_variable_name("") == "_var"

    def test_only_special_chars_returns_underscores(self):
        # All special chars become underscores, no leading digit, so kept as-is
        result = sanitize_variable_name("@#$")
        assert result == "___"

    def test_unicode_replaced(self):
        result = sanitize_variable_name("café")
        # 'é' is not [a-zA-Z0-9_] so it becomes '_'
        assert result == "caf_"

    def test_already_valid_with_numbers(self):
        assert sanitize_variable_name("var123") == "var123"

    def test_single_letter(self):
        assert sanitize_variable_name("x") == "x"

    def test_underscore_only(self):
        assert sanitize_variable_name("_") == "_"

    def test_mixed_valid_and_invalid(self):
        result = sanitize_variable_name("hello world-42")
        assert result == "hello_world_42"

    def test_leading_underscore_preserved(self):
        assert sanitize_variable_name("_private") == "_private"


# ---------------------------------------------------------------------------
# estimate_cell_lines
# ---------------------------------------------------------------------------


class TestEstimateCellLines:
    """Tests for estimate_cell_lines()."""

    def test_empty_string_returns_1(self):
        assert estimate_cell_lines("") == 1

    def test_single_line_no_newline_returns_1(self):
        assert estimate_cell_lines("x = 1") == 1

    def test_two_lines(self):
        assert estimate_cell_lines("line1\nline2") == 2

    def test_three_lines(self):
        assert estimate_cell_lines("a\nb\nc") == 3

    def test_trailing_newline_counts_extra_line(self):
        # "a\n" has one newline, so count = 1 + 1 = 2
        assert estimate_cell_lines("a\n") == 2

    def test_multiline_code(self):
        source = "def foo():\n    return 1\n\nfoo()"
        # 3 newlines => 4 lines
        assert estimate_cell_lines(source) == 4

    def test_minimum_is_1_for_nonempty(self):
        assert estimate_cell_lines("x") >= 1

    def test_many_newlines(self):
        source = "\n" * 9  # 9 newlines => 10 lines
        assert estimate_cell_lines(source) == 10

    def test_single_newline(self):
        assert estimate_cell_lines("\n") == 2
