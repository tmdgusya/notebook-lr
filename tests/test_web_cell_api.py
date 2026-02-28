"""Tests for web API cell operation endpoints."""

import pytest
from notebook_lr import Cell, CellType


class TestApiNotebook:
    def test_get_empty_notebook(self, web_app):
        client, nb, kernel = web_app
        resp = client.get("/api/notebook")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data["cells"], list)
        assert "metadata" in data and "version" in data

    def test_notebook_reflects_cells(self, web_app):
        client, nb, kernel = web_app
        nb.insert_cell(0, Cell(type=CellType.CODE, source="x = 1"))
        resp = client.get("/api/notebook")
        data = resp.get_json()
        assert len(data["cells"]) == 1
        assert data["cells"][0]["source"] == "x = 1"

    def test_cell_dict_structure(self, web_app):
        client, nb, kernel = web_app
        nb.insert_cell(0, Cell(type=CellType.CODE, source="print('hi')"))
        c = client.get("/api/notebook").get_json()["cells"][0]
        for key in ("index", "id", "type", "source", "outputs", "execution_count", "comments"):
            assert key in c


class TestApiCellAdd:
    def test_add_code_cell(self, web_app):
        client, nb, kernel = web_app
        resp = client.post("/api/cell/add", json={"type": "code"})
        assert resp.status_code == 200
        assert resp.get_json()["cell"]["type"] == "code"
        assert len(nb.cells) == 1

    def test_add_markdown_cell(self, web_app):
        client, nb, kernel = web_app
        resp = client.post("/api/cell/add", json={"type": "markdown"})
        assert resp.get_json()["cell"]["type"] == "markdown"

    def test_add_cell_after_index(self, web_app):
        client, nb, kernel = web_app
        client.post("/api/cell/add", json={"type": "code"})
        client.post("/api/cell/add", json={"type": "code"})
        resp = client.post("/api/cell/add", json={"type": "markdown", "after_index": 0})
        assert resp.get_json()["index"] == 1
        assert nb.cells[1].type == CellType.MARKDOWN

    def test_add_cell_default_type_is_code(self, web_app):
        client, nb, kernel = web_app
        resp = client.post("/api/cell/add", json={})
        assert resp.get_json()["cell"]["type"] == "code"


class TestApiCellDelete:
    def test_delete_existing_cell(self, web_app):
        client, nb, kernel = web_app
        client.post("/api/cell/add", json={"type": "code"})
        resp = client.post("/api/cell/delete", json={"index": 0})
        assert resp.get_json()["ok"] is True
        assert len(nb.cells) == 0

    def test_delete_invalid_index(self, web_app):
        client, nb, kernel = web_app
        resp = client.post("/api/cell/delete", json={"index": 99})
        assert resp.status_code == 400

    def test_delete_negative_index(self, web_app):
        client, nb, kernel = web_app
        assert client.post("/api/cell/delete", json={"index": -1}).status_code == 400

    def test_delete_middle_cell(self, web_app):
        client, nb, kernel = web_app
        for _ in range(3):
            client.post("/api/cell/add", json={"type": "code"})
        nb.cells[0].source = "first"
        nb.cells[1].source = "second"
        nb.cells[2].source = "third"
        client.post("/api/cell/delete", json={"index": 1})
        assert len(nb.cells) == 2
        assert nb.cells[0].source == "first"
        assert nb.cells[1].source == "third"


class TestApiCellMove:
    def test_move_cell_up(self, web_app):
        client, nb, kernel = web_app
        client.post("/api/cell/add", json={"type": "code"})
        client.post("/api/cell/add", json={"type": "code"})
        nb.cells[0].source = "first"
        nb.cells[1].source = "second"
        data = client.post("/api/cell/move", json={"index": 1, "direction": "up"}).get_json()
        assert data["ok"] is True and data["new_index"] == 0
        assert nb.cells[0].source == "second"

    def test_move_cell_down(self, web_app):
        client, nb, kernel = web_app
        client.post("/api/cell/add", json={"type": "code"})
        client.post("/api/cell/add", json={"type": "code"})
        nb.cells[0].source = "first"
        nb.cells[1].source = "second"
        data = client.post("/api/cell/move", json={"index": 0, "direction": "down"}).get_json()
        assert data["ok"] is True and data["new_index"] == 1
        assert nb.cells[0].source == "second"

    def test_move_first_up_fails(self, web_app):
        client, nb, kernel = web_app
        client.post("/api/cell/add", json={"type": "code"})
        client.post("/api/cell/add", json={"type": "code"})
        assert client.post("/api/cell/move", json={"index": 0, "direction": "up"}).status_code == 400

    def test_move_last_down_fails(self, web_app):
        client, nb, kernel = web_app
        client.post("/api/cell/add", json={"type": "code"})
        client.post("/api/cell/add", json={"type": "code"})
        assert client.post("/api/cell/move", json={"index": 1, "direction": "down"}).status_code == 400


class TestApiCellUpdate:
    def test_update_cell_source(self, web_app):
        client, nb, kernel = web_app
        client.post("/api/cell/add", json={"type": "code"})
        resp = client.post("/api/cell/update", json={"index": 0, "source": "x = 42"})
        assert resp.get_json()["ok"] is True
        assert nb.cells[0].source == "x = 42"

    def test_update_invalid_index(self, web_app):
        client, nb, kernel = web_app
        assert client.post("/api/cell/update", json={"index": 99, "source": "x"}).status_code == 400


class TestApiCellExecute:
    def test_execute_code_cell(self, web_app):
        client, nb, kernel = web_app
        client.post("/api/cell/add", json={"type": "code"})
        nb.cells[0].source = "2 + 2"
        data = client.post("/api/cell/execute", json={"index": 0}).get_json()
        assert data["success"] is True
        assert "outputs" in data and "execution_count" in data

    def test_execute_with_source_override(self, web_app):
        client, nb, kernel = web_app
        client.post("/api/cell/add", json={"type": "code"})
        data = client.post("/api/cell/execute", json={"index": 0, "source": "x = 10"}).get_json()
        assert data["success"] is True
        assert nb.cells[0].source == "x = 10"

    def test_execute_markdown_cell(self, web_app):
        client, nb, kernel = web_app
        client.post("/api/cell/add", json={"type": "markdown"})
        nb.cells[0].source = "# Hello"
        data = client.post("/api/cell/execute", json={"index": 0}).get_json()
        assert data["success"] is True
        assert data["outputs"] == [] and data["execution_count"] is None

    def test_execute_invalid_index(self, web_app):
        client, nb, kernel = web_app
        assert client.post("/api/cell/execute", json={"index": 99}).status_code == 400

    def test_execute_error_code(self, web_app):
        client, nb, kernel = web_app
        client.post("/api/cell/add", json={"type": "code"})
        data = client.post("/api/cell/execute", json={"index": 0, "source": "1/0"}).get_json()
        assert data["success"] is False and data["error"] is not None

    def test_execute_stores_outputs(self, web_app):
        client, nb, kernel = web_app
        client.post("/api/cell/add", json={"type": "code"})
        client.post("/api/cell/execute", json={"index": 0, "source": "print('test')"})
        assert nb.cells[0].execution_count is not None
        assert isinstance(nb.cells[0].outputs, list)

    def test_execute_output_text_fields(self, web_app):
        client, nb, kernel = web_app
        client.post("/api/cell/add", json={"type": "code"})
        data = client.post("/api/cell/execute", json={"index": 0, "source": "print('hello')"}).get_json()
        assert "output_text" in data and "error_text" in data


class TestApiExecuteAll:
    def test_execute_all_empty(self, web_app):
        client, nb, kernel = web_app
        data = client.post("/api/execute-all").get_json()
        assert data["results"] == []

    def test_execute_all_code_cells(self, web_app):
        client, nb, kernel = web_app
        client.post("/api/cell/add", json={"type": "code"})
        client.post("/api/cell/add", json={"type": "code"})
        nb.cells[0].source = "x = 1"
        nb.cells[1].source = "y = 2"
        data = client.post("/api/execute-all").get_json()
        assert len(data["results"]) == 2

    def test_execute_all_skips_markdown(self, web_app):
        client, nb, kernel = web_app
        client.post("/api/cell/add", json={"type": "code"})
        client.post("/api/cell/add", json={"type": "markdown"})
        client.post("/api/cell/add", json={"type": "code"})
        nb.cells[0].source = "x = 1"
        nb.cells[1].source = "# md"
        nb.cells[2].source = "y = 2"
        data = client.post("/api/execute-all").get_json()
        assert len(data["results"]) == 2
        assert data["results"][0]["index"] == 0 and data["results"][1]["index"] == 2

    def test_execute_all_stops_on_error(self, web_app):
        client, nb, kernel = web_app
        for _ in range(3):
            client.post("/api/cell/add", json={"type": "code"})
        nb.cells[0].source = "x = 1"
        nb.cells[1].source = "1/0"
        nb.cells[2].source = "y = 2"
        data = client.post("/api/execute-all").get_json()
        assert len(data["results"]) == 2
        assert data["results"][1]["success"] is False


class TestApiNotebookInfo:
    def test_info_empty(self, web_app):
        client, nb, kernel = web_app
        data = client.get("/api/notebook-info").get_json()
        assert data["cell_count"] == 0 and data["code_count"] == 0

    def test_info_with_cells(self, web_app):
        client, nb, kernel = web_app
        client.post("/api/cell/add", json={"type": "code"})
        client.post("/api/cell/add", json={"type": "code"})
        client.post("/api/cell/add", json={"type": "markdown"})
        data = client.get("/api/notebook-info").get_json()
        assert data["cell_count"] == 3
        assert data["code_count"] == 2 and data["md_count"] == 1

    def test_info_executed_count(self, web_app):
        client, nb, kernel = web_app
        client.post("/api/cell/add", json={"type": "code"})
        client.post("/api/cell/add", json={"type": "code"})
        client.post("/api/cell/execute", json={"index": 0, "source": "x = 1"})
        assert client.get("/api/notebook-info").get_json()["executed_count"] == 1
