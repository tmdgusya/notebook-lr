"""Tests for web API /api/save and /api/load endpoints."""

import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from notebook_lr import Notebook, Cell, CellType


class TestApiSave:
    def test_save_returns_200(self, web_app, tmp_path):
        client, nb, kernel = web_app
        nb.metadata["path"] = str(tmp_path / "notebook.nblr")
        resp = client.post("/api/save", json={})
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "saved"

    def test_save_creates_file(self, web_app, tmp_path):
        client, nb, kernel = web_app
        nb.metadata["path"] = str(tmp_path / "notebook.nblr")
        client.post("/api/save", json={})
        assert Path(nb.metadata["path"]).exists()

    def test_saved_file_is_valid_json(self, web_app, tmp_path):
        client, nb, kernel = web_app
        nb.metadata["path"] = str(tmp_path / "notebook.nblr")
        client.post("/api/save", json={})
        with open(nb.metadata["path"]) as f:
            data = json.load(f)
        assert "version" in data and "cells" in data

    def test_save_with_session(self, web_app, tmp_path):
        client, nb, kernel = web_app
        nb.metadata["path"] = str(tmp_path / "notebook.nblr")
        with patch.object(kernel, "get_namespace", return_value={"x": 1}):
            resp = client.post("/api/save", json={"include_session": True})
        assert resp.get_json()["status"] == "saved (with session)"

    def test_save_without_session_no_session_state(self, web_app, tmp_path):
        client, nb, kernel = web_app
        nb.metadata["path"] = str(tmp_path / "notebook.nblr")
        client.post("/api/save", json={})
        with open(nb.metadata["path"]) as f:
            assert json.load(f).get("session_state") is None

    def test_save_preserves_cells(self, web_app, tmp_path):
        client, nb, kernel = web_app
        nb.metadata["path"] = str(tmp_path / "notebook.nblr")
        nb.add_cell(Cell(source="z = 42"))
        client.post("/api/save", json={})
        with open(nb.metadata["path"]) as f:
            data = json.load(f)
        assert data["cells"][0]["source"] == "z = 42"


def _make_nblr_bytes(name="Test", cells=None):
    nb = Notebook.new(name=name)
    if cells:
        for cell in cells:
            nb.add_cell(cell)
    return json.dumps(nb.to_dict()).encode()


class TestApiLoad:
    def test_load_valid_nblr(self, web_app):
        client, nb, kernel = web_app
        data = {"file": (io.BytesIO(_make_nblr_bytes(name="Loaded")), "test.nblr")}
        resp = client.post("/api/load", data=data, content_type="multipart/form-data")
        assert resp.status_code == 200
        result = resp.get_json()
        assert "cells" in result and "metadata" in result

    def test_load_no_file_400(self, web_app):
        client, nb, kernel = web_app
        resp = client.post("/api/load", data={}, content_type="multipart/form-data")
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "no file provided"

    def test_load_empty_filename_400(self, web_app):
        client, nb, kernel = web_app
        data = {"file": (io.BytesIO(b"{}"), "")}
        resp = client.post("/api/load", data=data, content_type="multipart/form-data")
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "empty filename"

    def test_load_sets_metadata_path(self, web_app):
        client, nb, kernel = web_app
        data = {"file": (io.BytesIO(_make_nblr_bytes()), "mynotebook.nblr")}
        resp = client.post("/api/load", data=data, content_type="multipart/form-data")
        assert resp.get_json()["metadata"]["path"] == "mynotebook.nblr"

    def test_load_with_cells(self, web_app):
        client, nb, kernel = web_app
        src_nb = Notebook.new()
        src_nb.add_cell(Cell(source="import os"))
        src_nb.add_cell(Cell(type=CellType.MARKDOWN, source="# Title"))
        data = {"file": (io.BytesIO(json.dumps(src_nb.to_dict()).encode()), "cells.nblr")}
        result = client.post("/api/load", data=data, content_type="multipart/form-data").get_json()
        assert len(result["cells"]) == 2
        assert result["cells"][1]["type"] == "markdown"

    def test_load_preserves_execution_count(self, web_app):
        client, nb, kernel = web_app
        src_nb = Notebook.new()
        src_nb.add_cell(Cell(source="1+1", execution_count=5))
        data = {"file": (io.BytesIO(json.dumps(src_nb.to_dict()).encode()), "exec.nblr")}
        result = client.post("/api/load", data=data, content_type="multipart/form-data").get_json()
        assert result["cells"][0]["execution_count"] == 5


class TestSaveLoadRoundtrip:
    def test_roundtrip_preserves_source(self, web_app, tmp_path):
        client, nb, kernel = web_app
        nb.metadata["path"] = str(tmp_path / "notebook.nblr")
        nb.add_cell(Cell(source="round_trip = 'hello'"))
        client.post("/api/save", json={})
        with open(nb.metadata["path"], "rb") as f:
            file_bytes = f.read()
        data = {"file": (io.BytesIO(file_bytes), "round_trip.nblr")}
        result = client.post("/api/load", data=data, content_type="multipart/form-data").get_json()
        assert result["cells"][0]["source"] == "round_trip = 'hello'"
