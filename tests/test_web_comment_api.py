"""Tests for web API comment and variables endpoints."""

from unittest.mock import patch, MagicMock
import pytest
from notebook_lr import Cell, CellType
from notebook_lr.notebook import Comment


class TestCommentAdd:
    def test_add_comment_returns_ok(self, web_app):
        client, nb, kernel = web_app
        cell = Cell(type=CellType.CODE, source="x = 1")
        nb.insert_cell(0, cell)

        with patch("subprocess.run") as mock_sub, \
             patch("os.path.isfile", return_value=True):
            mock_sub.return_value = MagicMock(returncode=0, stdout="AI answer", stderr="")
            resp = client.post("/api/cell/comment/add", json={
                "cell_id": cell.id, "selected_text": "x = 1",
                "user_comment": "What does this do?", "provider": "claude",
            })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True and "comment" in data

    def test_add_comment_nonexistent_cell_404(self, web_app):
        client, nb, kernel = web_app
        with patch("subprocess.run") as mock_sub, \
             patch("os.path.isfile", return_value=True):
            mock_sub.return_value = MagicMock(returncode=0, stdout="AI", stderr="")
            resp = client.post("/api/cell/comment/add", json={
                "cell_id": "nonexistent", "selected_text": "x", "user_comment": "?",
            })
        assert resp.status_code == 404

    def test_add_comment_invalid_provider_defaults_to_claude(self, web_app):
        client, nb, kernel = web_app
        cell = Cell(type=CellType.CODE, source="")
        nb.insert_cell(0, cell)

        with patch("subprocess.run") as mock_sub, \
             patch("os.path.isfile", return_value=True):
            mock_sub.return_value = MagicMock(returncode=0, stdout="answer", stderr="")
            resp = client.post("/api/cell/comment/add", json={
                "cell_id": cell.id, "selected_text": "z",
                "user_comment": "?", "provider": "invalid_provider",
            })
        assert resp.get_json()["comment"]["provider"] == "claude"

    def test_add_comment_resolved_status(self, web_app):
        client, nb, kernel = web_app
        cell = Cell(type=CellType.CODE, source="")
        nb.insert_cell(0, cell)

        with patch("subprocess.run") as mock_sub, \
             patch("os.path.isfile", return_value=True):
            mock_sub.return_value = MagicMock(returncode=0, stdout="Great explanation", stderr="")
            resp = client.post("/api/cell/comment/add", json={
                "cell_id": cell.id, "selected_text": "a + b",
                "user_comment": "Add?", "provider": "claude",
            })
        data = resp.get_json()
        assert data["comment"]["status"] == "resolved"
        assert data["comment"]["ai_response"] == "Great explanation"


class TestCommentDelete:
    def _add_comment(self, cell):
        comment = Comment(
            from_line=0, from_ch=0, to_line=0, to_ch=5,
            selected_text="x = 1", user_comment="What?",
            ai_response="It assigns 1.", status="resolved",
        )
        cell.comments.append(comment)
        return comment

    def test_delete_existing_comment(self, web_app):
        client, nb, kernel = web_app
        cell = Cell(type=CellType.CODE, source="")
        nb.insert_cell(0, cell)
        comment = self._add_comment(cell)
        resp = client.post("/api/cell/comment/delete", json={
            "cell_id": cell.id, "comment_id": comment.id,
        })
        assert resp.get_json()["ok"] is True
        assert len(cell.comments) == 0

    def test_delete_nonexistent_cell_404(self, web_app):
        client, nb, kernel = web_app
        resp = client.post("/api/cell/comment/delete", json={
            "cell_id": "no-such-cell", "comment_id": "cmt_123",
        })
        assert resp.status_code == 404

    def test_delete_nonexistent_comment_noop(self, web_app):
        client, nb, kernel = web_app
        cell = Cell(type=CellType.CODE, source="")
        nb.insert_cell(0, cell)
        resp = client.post("/api/cell/comment/delete", json={
            "cell_id": cell.id, "comment_id": "cmt_doesnotexist",
        })
        assert resp.get_json()["ok"] is True


class TestVariables:
    def test_no_variables_empty_list(self, web_app):
        client, nb, kernel = web_app
        data = client.get("/api/variables").get_json()
        assert isinstance(data["variables"], list)

    def test_variables_after_execution(self, web_app):
        client, nb, kernel = web_app
        client.post("/api/cell/add", json={"type": "code"})
        nb.cells[0].source = "alpha = 42"
        client.post("/api/cell/execute", json={"index": 0})
        names = [v["name"] for v in client.get("/api/variables").get_json()["variables"]]
        assert "alpha" in names

    def test_variable_truncated_if_long(self, web_app):
        client, nb, kernel = web_app
        client.post("/api/cell/add", json={"type": "code"})
        nb.cells[0].source = "long_var = 'x' * 300"
        client.post("/api/cell/execute", json={"index": 0})
        var = next(v for v in client.get("/api/variables").get_json()["variables"] if v["name"] == "long_var")
        assert len(var["value"]) <= 200

    def test_variable_has_name_type_value(self, web_app):
        client, nb, kernel = web_app
        client.post("/api/cell/add", json={"type": "code"})
        nb.cells[0].source = "my_int = 7"
        client.post("/api/cell/execute", json={"index": 0})
        var = next(v for v in client.get("/api/variables").get_json()["variables"] if v["name"] == "my_int")
        assert var["type"] == "int" and var["value"] == "7"


class TestClearVariables:
    def test_clear_returns_ok(self, web_app):
        client, nb, kernel = web_app
        assert client.post("/api/clear-variables").get_json()["ok"] is True

    def test_clear_removes_variables(self, web_app):
        client, nb, kernel = web_app
        client.post("/api/cell/add", json={"type": "code"})
        nb.cells[0].source = "temp_var = 99"
        client.post("/api/cell/execute", json={"index": 0})
        client.post("/api/clear-variables")
        names = [v["name"] for v in client.get("/api/variables").get_json()["variables"]]
        assert "temp_var" not in names
