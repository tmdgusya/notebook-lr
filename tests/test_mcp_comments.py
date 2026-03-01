"""Tests for comment-related MCP tools in notebook_lr.mcp_server."""

import pytest

from notebook_lr.mcp_server import (
    add_cell,
    get_cell_comments,
    get_notebook_context,
    get_notebook,
    _reset_notebook,
)
from notebook_lr.notebook import Comment


def _add_comment(cell, user_comment="test question", status="resolved"):
    comment = Comment(
        from_line=0, from_ch=0, to_line=0, to_ch=5,
        selected_text="x = 1",
        user_comment=user_comment,
        ai_response="AI answer",
        status=status,
    )
    cell.comments.append(comment)
    return comment


class TestGetCellComments:
    def test_returns_empty_list_when_no_comments(self):
        add_cell(source="x = 1")
        result = get_cell_comments(index=0)
        assert result == []

    def test_returns_comments_for_cell_with_one_comment(self):
        add_cell(source="x = 1")
        nb = get_notebook()
        cell = nb.get_cell(0)
        _add_comment(cell, user_comment="What does x do?")
        result = get_cell_comments(index=0)
        assert len(result) == 1
        assert result[0]["user_comment"] == "What does x do?"

    def test_returns_all_comments_for_cell_with_multiple(self):
        add_cell(source="x = 1")
        nb = get_notebook()
        cell = nb.get_cell(0)
        _add_comment(cell, user_comment="First question")
        _add_comment(cell, user_comment="Second question")
        result = get_cell_comments(index=0)
        assert len(result) == 2
        user_comments = [c["user_comment"] for c in result]
        assert "First question" in user_comments
        assert "Second question" in user_comments

    def test_returns_dicts_with_expected_fields(self):
        add_cell(source="x = 1")
        nb = get_notebook()
        cell = nb.get_cell(0)
        _add_comment(cell, user_comment="Explain?", status="resolved")
        result = get_cell_comments(index=0)
        assert len(result) == 1
        comment_dict = result[0]
        assert "user_comment" in comment_dict
        assert "status" in comment_dict
        assert "selected_text" in comment_dict
        assert "ai_response" in comment_dict

    def test_comments_isolated_per_cell(self):
        add_cell(source="x = 1")
        add_cell(source="y = 2")
        nb = get_notebook()
        _add_comment(nb.get_cell(0), user_comment="question on cell 0")
        result_cell_1 = get_cell_comments(index=1)
        assert result_cell_1 == []

    def test_raises_for_invalid_index(self):
        with pytest.raises(ValueError):
            get_cell_comments(index=999)

    def test_raises_for_negative_index(self):
        with pytest.raises(ValueError):
            get_cell_comments(index=-1)


class TestGetNotebookContext:
    def test_returns_dict_with_required_fields(self):
        add_cell(source="x = 1")
        result = get_notebook_context(index=0)
        assert isinstance(result, dict)
        for field in ("cell_index", "total_cells", "cell_type", "cell_source",
                      "cell_outputs", "previous_cell", "next_cell", "comments"):
            assert field in result, f"Missing field: {field}"

    def test_cell_index_and_total_cells(self):
        add_cell(source="a = 1")
        add_cell(source="b = 2")
        add_cell(source="c = 3")
        result = get_notebook_context(index=1)
        assert result["cell_index"] == 1
        assert result["total_cells"] == 3

    def test_cell_source_returned(self):
        add_cell(source="my_source = 42")
        result = get_notebook_context(index=0)
        assert result["cell_source"] == "my_source = 42"

    def test_cell_type_returned(self):
        add_cell(cell_type="markdown", source="# Header")
        result = get_notebook_context(index=0)
        assert result["cell_type"] == "markdown"

    def test_first_cell_has_no_previous(self):
        add_cell(source="first")
        add_cell(source="second")
        result = get_notebook_context(index=0)
        assert result["previous_cell"] is None

    def test_first_cell_has_next_neighbor(self):
        add_cell(source="first")
        add_cell(source="second cell source")
        result = get_notebook_context(index=0)
        assert result["next_cell"] is not None
        assert "second cell source" in result["next_cell"]["source_preview"]

    def test_last_cell_has_no_next(self):
        add_cell(source="first")
        add_cell(source="last")
        result = get_notebook_context(index=1)
        assert result["next_cell"] is None

    def test_last_cell_has_previous_neighbor(self):
        add_cell(source="previous cell source")
        add_cell(source="last")
        result = get_notebook_context(index=1)
        assert result["previous_cell"] is not None
        assert "previous cell source" in result["previous_cell"]["source_preview"]

    def test_middle_cell_has_both_neighbors(self):
        add_cell(source="alpha")
        add_cell(source="beta")
        add_cell(source="gamma")
        result = get_notebook_context(index=1)
        assert result["previous_cell"] is not None
        assert "alpha" in result["previous_cell"]["source_preview"]
        assert result["next_cell"] is not None
        assert "gamma" in result["next_cell"]["source_preview"]

    def test_single_cell_no_neighbors(self):
        add_cell(source="only")
        result = get_notebook_context(index=0)
        assert result["previous_cell"] is None
        assert result["next_cell"] is None

    def test_neighbor_summary_includes_type(self):
        add_cell(cell_type="markdown", source="# Intro")
        add_cell(source="x = 1")
        result = get_notebook_context(index=1)
        assert result["previous_cell"]["type"] == "markdown"

    def test_comments_empty_when_no_comments(self):
        add_cell(source="x = 1")
        result = get_notebook_context(index=0)
        assert result["comments"] == []

    def test_comments_included_when_present(self):
        add_cell(source="x = 1")
        nb = get_notebook()
        cell = nb.get_cell(0)
        _add_comment(cell, user_comment="Why x?", status="resolved")
        result = get_notebook_context(index=0)
        assert len(result["comments"]) == 1
        assert result["comments"][0]["user_comment"] == "Why x?"
        assert result["comments"][0]["status"] == "resolved"

    def test_comments_contain_selected_text(self):
        add_cell(source="x = 1")
        nb = get_notebook()
        cell = nb.get_cell(0)
        comment = Comment(
            from_line=0, from_ch=0, to_line=0, to_ch=5,
            selected_text="x = 1",
            user_comment="Explain?",
            status="pending",
        )
        cell.comments.append(comment)
        result = get_notebook_context(index=0)
        assert result["comments"][0]["selected_text"] == "x = 1"

    def test_raises_for_invalid_index(self):
        with pytest.raises(ValueError):
            get_notebook_context(index=999)

    def test_raises_for_negative_index(self):
        with pytest.raises(ValueError):
            get_notebook_context(index=-1)

    def test_cell_outputs_returned(self):
        add_cell(source="print('hi')")
        nb = get_notebook()
        cell = nb.get_cell(0)
        cell.outputs = [{"type": "stream", "text": "hi\n"}]
        result = get_notebook_context(index=0)
        assert len(result["cell_outputs"]) == 1
        assert result["cell_outputs"][0]["text"] == "hi\n"

    def test_cell_outputs_capped_at_three(self):
        add_cell(source="x = 1")
        nb = get_notebook()
        cell = nb.get_cell(0)
        cell.outputs = [{"type": "stream", "text": f"out{i}\n"} for i in range(10)]
        result = get_notebook_context(index=0)
        assert len(result["cell_outputs"]) == 3
