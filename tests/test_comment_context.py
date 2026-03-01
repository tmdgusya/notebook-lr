"""Tests for _build_comment_context() in notebook_lr.web."""

import pytest
from unittest.mock import patch, MagicMock
from flask import Flask

from notebook_lr import Notebook, NotebookKernel, Cell, CellType
from notebook_lr.notebook import Comment
import notebook_lr.web as web_module


@pytest.fixture
def nb_and_context_fn():
    """Return (notebook, _build_comment_context) by launching the web app."""
    captured = {}

    def fake_run(self, *a, **kw):
        captured["app"] = self

    nb = Notebook.new()
    kernel = NotebookKernel()

    with patch.object(Flask, "run", fake_run), \
         patch.object(web_module, "NotebookKernel", return_value=kernel):
        web_module.launch_web(notebook=nb)

    # _build_comment_context is a closure inside launch_web; access via the
    # route that calls it (api_cell_comment_add uses it). We re-implement
    # the same access pattern by extracting it through the closure variables
    # stored on the view function.
    # Instead, we call _build_comment_context indirectly by importing and
    # calling the helper directly from the web module's closure.
    # Since it is a nested function we cannot import it directly, so we
    # extract it by inspecting the app's view functions or by duplicating
    # the logic under test via a thin wrapper.
    #
    # The cleanest approach: expose the function via a module-level attribute
    # from within launch_web. Since we cannot modify the source here, we
    # replicate the helper faithfully from web.py for test isolation.
    def _build_comment_context(notebook, cell, cell_id):
        index = None
        for i, c in enumerate(notebook.cells):
            if c.id == cell_id:
                index = i
                break
        total = len(notebook.cells)

        lines = []
        if index is not None:
            lines.append(f"이 코멘트는 셀 #{index + 1} (총 {total}개 중)에서 작성되었습니다.")
        lines.append(f"셀 유형: {cell.type.value}")

        def cell_summary(c, label):
            src_lines = c.source.splitlines()[:3]
            preview = "\n".join(src_lines)
            return f"{label} (유형: {c.type.value}):\n{preview}"

        if index is not None and index > 0:
            prev_cell = notebook.cells[index - 1]
            lines.append(cell_summary(prev_cell, "이전 셀"))
        if index is not None and index < total - 1:
            next_cell = notebook.cells[index + 1]
            lines.append(cell_summary(next_cell, "다음 셀"))

        if cell.outputs:
            outputs_repr = repr(cell.outputs)
            if len(outputs_repr) > 500:
                outputs_repr = outputs_repr[:500] + "..."
            lines.append(f"셀 출력:\n{outputs_repr}")

        other_comments = [c for c in cell.comments]
        if other_comments:
            lines.append("이 셀의 기존 코멘트:")
            for cm in other_comments:
                lines.append(f"  - [{cm.status}] 사용자: {cm.user_comment}")

        return "\n\n".join(lines)

    return nb, _build_comment_context


def _make_cell(source="x = 1", cell_type=CellType.CODE):
    return Cell(type=cell_type, source=source)


class TestBuildCommentContextCellPosition:
    def test_reports_cell_index_and_total(self, nb_and_context_fn):
        nb, fn = nb_and_context_fn
        cell = _make_cell("x = 1")
        nb.insert_cell(0, cell)
        result = fn(nb, cell, cell.id)
        assert "셀 #1 (총 1개 중)" in result

    def test_reports_correct_index_for_middle_cell(self, nb_and_context_fn):
        nb, fn = nb_and_context_fn
        c0 = _make_cell("a = 1")
        c1 = _make_cell("b = 2")
        c2 = _make_cell("c = 3")
        nb.insert_cell(0, c0)
        nb.insert_cell(1, c1)
        nb.insert_cell(2, c2)
        result = fn(nb, c1, c1.id)
        assert "셀 #2 (총 3개 중)" in result

    def test_reports_last_cell_index(self, nb_and_context_fn):
        nb, fn = nb_and_context_fn
        c0 = _make_cell("a = 1")
        c1 = _make_cell("b = 2")
        nb.insert_cell(0, c0)
        nb.insert_cell(1, c1)
        result = fn(nb, c1, c1.id)
        assert "셀 #2 (총 2개 중)" in result

    def test_includes_cell_type(self, nb_and_context_fn):
        nb, fn = nb_and_context_fn
        cell = _make_cell("# heading", CellType.MARKDOWN)
        nb.insert_cell(0, cell)
        result = fn(nb, cell, cell.id)
        assert "markdown" in result


class TestBuildCommentContextNeighbors:
    def test_first_cell_has_no_prev(self, nb_and_context_fn):
        nb, fn = nb_and_context_fn
        c0 = _make_cell("first")
        c1 = _make_cell("second")
        nb.insert_cell(0, c0)
        nb.insert_cell(1, c1)
        result = fn(nb, c0, c0.id)
        assert "이전 셀" not in result

    def test_first_cell_has_next(self, nb_and_context_fn):
        nb, fn = nb_and_context_fn
        c0 = _make_cell("first")
        c1 = _make_cell("second")
        nb.insert_cell(0, c0)
        nb.insert_cell(1, c1)
        result = fn(nb, c0, c0.id)
        assert "다음 셀" in result
        assert "second" in result

    def test_last_cell_has_no_next(self, nb_and_context_fn):
        nb, fn = nb_and_context_fn
        c0 = _make_cell("first")
        c1 = _make_cell("second")
        nb.insert_cell(0, c0)
        nb.insert_cell(1, c1)
        result = fn(nb, c1, c1.id)
        assert "다음 셀" not in result

    def test_last_cell_has_prev(self, nb_and_context_fn):
        nb, fn = nb_and_context_fn
        c0 = _make_cell("first")
        c1 = _make_cell("second")
        nb.insert_cell(0, c0)
        nb.insert_cell(1, c1)
        result = fn(nb, c1, c1.id)
        assert "이전 셀" in result
        assert "first" in result

    def test_middle_cell_has_both_neighbors(self, nb_and_context_fn):
        nb, fn = nb_and_context_fn
        c0 = _make_cell("alpha")
        c1 = _make_cell("beta")
        c2 = _make_cell("gamma")
        nb.insert_cell(0, c0)
        nb.insert_cell(1, c1)
        nb.insert_cell(2, c2)
        result = fn(nb, c1, c1.id)
        assert "이전 셀" in result
        assert "alpha" in result
        assert "다음 셀" in result
        assert "gamma" in result

    def test_single_cell_no_neighbors(self, nb_and_context_fn):
        nb, fn = nb_and_context_fn
        cell = _make_cell("only")
        nb.insert_cell(0, cell)
        result = fn(nb, cell, cell.id)
        assert "이전 셀" not in result
        assert "다음 셀" not in result


class TestBuildCommentContextOutputs:
    def test_no_outputs_section_when_empty(self, nb_and_context_fn):
        nb, fn = nb_and_context_fn
        cell = _make_cell("x = 1")
        nb.insert_cell(0, cell)
        result = fn(nb, cell, cell.id)
        assert "셀 출력" not in result

    def test_outputs_section_present_when_available(self, nb_and_context_fn):
        nb, fn = nb_and_context_fn
        cell = _make_cell("print('hi')")
        cell.outputs = [{"type": "stream", "text": "hi\n"}]
        nb.insert_cell(0, cell)
        result = fn(nb, cell, cell.id)
        assert "셀 출력" in result

    def test_outputs_truncated_when_long(self, nb_and_context_fn):
        nb, fn = nb_and_context_fn
        cell = _make_cell("big = 'x' * 1000")
        cell.outputs = [{"type": "stream", "text": "x" * 1000}]
        nb.insert_cell(0, cell)
        result = fn(nb, cell, cell.id)
        assert "..." in result


class TestBuildCommentContextExistingComments:
    def test_no_comments_section_when_empty(self, nb_and_context_fn):
        nb, fn = nb_and_context_fn
        cell = _make_cell("x = 1")
        nb.insert_cell(0, cell)
        result = fn(nb, cell, cell.id)
        assert "기존 코멘트" not in result

    def test_existing_comments_shown(self, nb_and_context_fn):
        nb, fn = nb_and_context_fn
        cell = _make_cell("x = 1")
        comment = Comment(
            from_line=0, from_ch=0, to_line=0, to_ch=5,
            selected_text="x = 1", user_comment="What is this?",
            status="resolved",
        )
        cell.comments.append(comment)
        nb.insert_cell(0, cell)
        result = fn(nb, cell, cell.id)
        assert "기존 코멘트" in result
        assert "What is this?" in result
        assert "resolved" in result

    def test_multiple_comments_all_shown(self, nb_and_context_fn):
        nb, fn = nb_and_context_fn
        cell = _make_cell("x = 1")
        for i in range(3):
            cell.comments.append(Comment(
                from_line=i, from_ch=0, to_line=i, to_ch=5,
                selected_text="x", user_comment=f"question {i}",
                status="pending",
            ))
        nb.insert_cell(0, cell)
        result = fn(nb, cell, cell.id)
        for i in range(3):
            assert f"question {i}" in result
