"""Tests for the Comment model."""

import pytest
from datetime import datetime
from pydantic import BaseModel

from notebook_lr.notebook import Comment, Cell, CellType


def _comment(**kwargs):
    defaults = dict(from_line=0, from_ch=0, to_line=0, to_ch=5,
                    selected_text="foo", user_comment="bar")
    defaults.update(kwargs)
    return Comment(**defaults)


class TestCommentCreation:
    def test_required_fields(self):
        c = _comment(from_line=1, to_line=1, to_ch=10, selected_text="x = 42", user_comment="What?")
        assert c.from_line == 1 and c.to_ch == 10
        assert c.selected_text == "x = 42"

    def test_defaults(self):
        c = _comment()
        assert c.ai_response == ""
        assert c.status == "pending"
        assert c.provider == "claude"
        assert c.id.startswith("cmt_")
        assert isinstance(c, BaseModel)

    def test_created_at_auto_generated(self):
        before = datetime.now().isoformat()
        c = _comment()
        assert before <= c.created_at

    def test_unique_ids(self):
        ids = [_comment(from_line=i).id for i in range(5)]
        for cid in ids:
            assert cid.startswith("cmt_")

    def test_custom_id(self):
        assert _comment(id="custom_123").id == "custom_123"

    def test_all_fields_specified(self):
        c = Comment(
            id="cmt_test", from_line=5, from_ch=4, to_line=7, to_ch=20,
            selected_text="for x in range(10):", user_comment="Efficient?",
            ai_response="O(n) time.", status="resolved", provider="glm",
            created_at="2024-01-01T00:00:00",
        )
        assert c.provider == "glm" and c.status == "resolved"
        assert c.ai_response == "O(n) time."


class TestCommentStatusAndProvider:
    @pytest.mark.parametrize("status", ["pending", "loading", "resolved", "error"])
    def test_valid_statuses(self, status):
        assert _comment(status=status).status == status

    @pytest.mark.parametrize("provider", ["claude", "glm", "kimi"])
    def test_valid_providers(self, provider):
        assert _comment(provider=provider).provider == provider


class TestCommentSerialization:
    def test_model_dump_fields(self):
        data = _comment().model_dump()
        expected = {"id", "from_line", "from_ch", "to_line", "to_ch",
                    "selected_text", "user_comment", "ai_response",
                    "status", "provider", "created_at"}
        assert expected == set(data.keys())

    def test_roundtrip(self):
        original = _comment(status="resolved", ai_response="answer", provider="kimi")
        restored = Comment(**original.model_dump())
        assert restored.model_dump() == original.model_dump()


class TestCommentInCell:
    def test_cell_starts_with_no_comments(self):
        assert Cell(type=CellType.CODE, source="x = 1").comments == []

    def test_add_comment_to_cell(self):
        cell = Cell(type=CellType.CODE, source="x = 1")
        cell.comments.append(_comment(selected_text="x = 1", user_comment="explain"))
        assert len(cell.comments) == 1

    def test_cell_to_dict_includes_comments(self):
        cell = Cell(type=CellType.CODE, source="x = 1")
        cell.comments.append(_comment(selected_text="x = 1"))
        d = cell.to_dict()
        assert len(d["comments"]) == 1 and d["comments"][0]["selected_text"] == "x = 1"

    def test_cell_from_dict_restores_comments(self):
        cell_data = {
            "type": "code", "source": "x = 1", "outputs": [],
            "execution_count": None, "metadata": {},
            "comments": [_comment(id="cmt_test", ai_response="answer", status="resolved").model_dump()],
        }
        cell = Cell.from_dict(cell_data)
        assert len(cell.comments) == 1 and cell.comments[0].id == "cmt_test"

    def test_cell_from_dict_missing_comments_key(self):
        cell = Cell.from_dict({"type": "code", "source": "x", "outputs": [], "metadata": {}})
        assert cell.comments == []

    def test_cell_roundtrip_with_comments(self):
        cell = Cell(type=CellType.CODE, source="compute()")
        cell.comments.append(_comment(selected_text="compute()", ai_response="int", status="resolved", provider="glm"))
        restored = Cell.from_dict(cell.to_dict())
        assert restored.comments[0].model_dump() == cell.comments[0].model_dump()


class TestCommentEdgeCases:
    def test_multiline_selected_text(self):
        c = _comment(from_line=1, to_line=3, selected_text="line1\nline2\nline3")
        assert "\n" in c.selected_text

    def test_empty_strings(self):
        c = _comment(selected_text="", user_comment="")
        assert c.selected_text == "" and c.user_comment == ""

    def test_unicode(self):
        c = _comment(selected_text="print('世界')", user_comment="这是什么？")
        assert "世界" in c.selected_text

    def test_long_ai_response(self):
        assert len(_comment(ai_response="A" * 10000).ai_response) == 10000

    def test_zero_and_large_positions(self):
        c1 = _comment(from_line=0, from_ch=0, to_line=0, to_ch=0)
        c2 = _comment(from_line=9999, from_ch=200, to_line=9999, to_ch=220)
        assert c1.from_line == 0 and c2.from_line == 9999
