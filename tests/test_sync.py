"""
Tests for file-based synchronization between MCP server and web server.

Covers:
- MCP server loading from NOTEBOOK_LR_PATH env var
- MCP auto-save on mutations (update, add, delete)
- MCP reload on external file changes (_maybe_reload)
- Web server /api/notebook/check-updates endpoint
- Web server auto-save on cell add/update
- Integration: MCP write -> file -> web read
"""

import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from flask import Flask

from notebook_lr import Notebook, Cell, CellType, NotebookKernel
from notebook_lr.mcp_server import (
    _reset_notebook,
    get_notebook,
    update_cell_source,
    add_cell,
    delete_cell,
    list_cells,
)
import notebook_lr.mcp_server as mcp_module
import notebook_lr.web as web_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_notebook_file(tmp_path: Path, sources: list[str] | None = None) -> Path:
    """Create a .nblr file with code cells from the given source strings."""
    nb = Notebook.new()
    for i, src in enumerate(sources or []):
        nb.insert_cell(i, Cell(type=CellType.CODE, source=src))
    path = tmp_path / "test.nblr"
    nb.save(path)
    return path


def _make_web_client(nb: Notebook):
    """Return (test_client, nb, kernel) using launch_web() routes without starting a server."""
    kernel = NotebookKernel()
    captured = {}

    def fake_run(self, *a, **kw):
        captured["app"] = self

    with patch.object(Flask, "run", fake_run), \
         patch.object(web_module, "NotebookKernel", return_value=kernel):
        web_module.launch_web(notebook=nb)

    app = captured["app"]
    app.config["TESTING"] = True
    return app.test_client(), nb, kernel


def _bump_mtime(path: Path, delta: float = 2.0) -> None:
    """Advance the mtime of a file by delta seconds to simulate an external change."""
    current = os.path.getmtime(path)
    os.utime(path, (current + delta, current + delta))


# ---------------------------------------------------------------------------
# MCP Server – env var loading
# ---------------------------------------------------------------------------

class TestMcpLoadsFromEnvVar:
    def test_loads_cells_from_file(self, tmp_path):
        """get_notebook() loads cells from file when NOTEBOOK_LR_PATH is set."""
        path = _make_notebook_file(tmp_path, ["x = 0", "x = 1"])

        with patch.dict(os.environ, {"NOTEBOOK_LR_PATH": str(path)}):
            nb = get_notebook()

        assert len(nb.cells) == 2
        assert nb.cells[0].source == "x = 0"
        assert nb.cells[1].source == "x = 1"

    def test_no_env_creates_empty_notebook(self, monkeypatch):
        """Without NOTEBOOK_LR_PATH, get_notebook() returns a fresh empty notebook."""
        monkeypatch.delenv("NOTEBOOK_LR_PATH", raising=False)

        nb = get_notebook()

        assert len(nb.cells) == 0
        assert mcp_module._notebook_path is None

    def test_env_path_missing_file_creates_empty_and_stores_path(self, tmp_path):
        """NOTEBOOK_LR_PATH pointing to missing file: create empty notebook, store path."""
        non_existent = str(tmp_path / "does_not_exist.nblr")

        with patch.dict(os.environ, {"NOTEBOOK_LR_PATH": non_existent}):
            nb = get_notebook()

        assert len(nb.cells) == 0
        assert mcp_module._notebook_path == non_existent

    def test_loads_mtime_on_initial_load(self, tmp_path):
        """After loading from file, _notebook_mtime reflects the file's mtime."""
        path = _make_notebook_file(tmp_path, ["a = 1"])
        expected_mtime = os.path.getmtime(path)

        with patch.dict(os.environ, {"NOTEBOOK_LR_PATH": str(path)}):
            get_notebook()

        assert mcp_module._notebook_mtime == expected_mtime


# ---------------------------------------------------------------------------
# MCP Server – auto-save on mutations
# ---------------------------------------------------------------------------

class TestMcpAutoSave:
    def test_auto_save_on_update_cell_source(self, tmp_path):
        """update_cell_source() persists the new source to disk."""
        path = _make_notebook_file(tmp_path, ["original"])

        with patch.dict(os.environ, {"NOTEBOOK_LR_PATH": str(path)}):
            update_cell_source(index=0, source="updated")

        assert Notebook.load(path).cells[0].source == "updated"

    def test_auto_save_on_add_cell(self, tmp_path):
        """add_cell() appends the new cell to the file on disk."""
        path = _make_notebook_file(tmp_path, ["existing"])

        with patch.dict(os.environ, {"NOTEBOOK_LR_PATH": str(path)}):
            add_cell(source="new_cell = True")

        saved = Notebook.load(path)
        assert len(saved.cells) == 2
        assert saved.cells[1].source == "new_cell = True"

    def test_auto_save_on_delete_cell(self, tmp_path):
        """delete_cell() removes the cell from the file on disk."""
        path = _make_notebook_file(tmp_path, ["keep", "delete_me"])

        with patch.dict(os.environ, {"NOTEBOOK_LR_PATH": str(path)}):
            delete_cell(index=1)

        saved = Notebook.load(path)
        assert len(saved.cells) == 1
        assert saved.cells[0].source == "keep"

    def test_no_auto_save_without_path(self, monkeypatch):
        """Mutations without NOTEBOOK_LR_PATH raise RuntimeError to prevent silent data loss."""
        monkeypatch.delenv("NOTEBOOK_LR_PATH", raising=False)

        get_notebook()
        with pytest.raises(RuntimeError, match="NOT saved to disk"):
            add_cell(source="test")

        assert mcp_module._notebook_path is None

    def test_auto_save_updates_mtime_tracking(self, tmp_path):
        """After auto-save, _notebook_mtime is refreshed so next read won't reload."""
        path = _make_notebook_file(tmp_path, ["v1"])

        with patch.dict(os.environ, {"NOTEBOOK_LR_PATH": str(path)}):
            get_notebook()
            update_cell_source(index=0, source="v2")
            mtime_after_save = mcp_module._notebook_mtime

        assert mtime_after_save == os.path.getmtime(path)


# ---------------------------------------------------------------------------
# MCP Server – external change detection (_maybe_reload)
# ---------------------------------------------------------------------------

class TestMcpReloadOnExternalChange:
    def test_list_cells_reloads_after_external_change(self, tmp_path):
        """list_cells() reloads when the file mtime changes externally."""
        path = _make_notebook_file(tmp_path, ["original"])

        with patch.dict(os.environ, {"NOTEBOOK_LR_PATH": str(path)}):
            get_notebook()

            # Write a new version externally and bump mtime
            nb2 = Notebook.new()
            nb2.insert_cell(0, Cell(type=CellType.CODE, source="original"))
            nb2.insert_cell(1, Cell(type=CellType.CODE, source="external_cell = 42"))
            nb2.save(path)
            _bump_mtime(path)

            result = list_cells()

        sources = [c.source for c in result.cells]
        assert "external_cell = 42" in sources

    def test_no_reload_when_mtime_unchanged(self, tmp_path):
        """list_cells() does NOT reload if the file mtime hasn't changed."""
        path = _make_notebook_file(tmp_path, ["original"])

        with patch.dict(os.environ, {"NOTEBOOK_LR_PATH": str(path)}):
            nb = get_notebook()
            # Mutate in-memory without touching the file
            nb.cells[0].source = "in_memory_only"

            result = list_cells()

        # Should reflect in-memory state (no reload triggered)
        assert result.cells[0].source == "in_memory_only"

    def test_reload_updates_mtime_tracking(self, tmp_path):
        """After reload, _notebook_mtime is updated to the new file mtime."""
        path = _make_notebook_file(tmp_path, ["v1"])

        with patch.dict(os.environ, {"NOTEBOOK_LR_PATH": str(path)}):
            get_notebook()
            old_mtime = mcp_module._notebook_mtime

            nb2 = Notebook.new()
            nb2.insert_cell(0, Cell(type=CellType.CODE, source="v2"))
            nb2.save(path)
            _bump_mtime(path)

            list_cells()
            new_mtime = mcp_module._notebook_mtime

        assert new_mtime > old_mtime
        assert new_mtime == os.path.getmtime(path)


# ---------------------------------------------------------------------------
# MCP Server – _reset_notebook
# ---------------------------------------------------------------------------

class TestMcpReset:
    def test_reset_clears_all_global_state(self, tmp_path):
        """_reset_notebook() clears _notebook, _notebook_path, and _notebook_mtime."""
        path = _make_notebook_file(tmp_path, ["x = 1"])

        with patch.dict(os.environ, {"NOTEBOOK_LR_PATH": str(path)}):
            get_notebook()

        assert mcp_module._notebook is not None
        assert mcp_module._notebook_path is not None
        assert mcp_module._notebook_mtime != 0.0

        _reset_notebook()

        assert mcp_module._notebook is None
        assert mcp_module._notebook_path is None
        assert mcp_module._notebook_mtime == 0.0

    def test_reset_allows_fresh_load_from_env(self, tmp_path):
        """After _reset_notebook(), next get_notebook() reads NOTEBOOK_LR_PATH again."""
        path = _make_notebook_file(tmp_path, ["first"])

        with patch.dict(os.environ, {"NOTEBOOK_LR_PATH": str(path)}):
            get_notebook()
            _reset_notebook()

            # Update the file before next load
            nb2 = Notebook.new()
            nb2.insert_cell(0, Cell(type=CellType.CODE, source="second"))
            nb2.save(path)

            nb = get_notebook()

        assert nb.cells[0].source == "second"


# ---------------------------------------------------------------------------
# Web Server – /api/notebook/check-updates
# ---------------------------------------------------------------------------

class TestWebCheckUpdates:
    def test_no_change_when_mtime_same(self, tmp_path):
        """check-updates returns changed=false when file mtime matches recorded mtime."""
        path = _make_notebook_file(tmp_path, ["x = 1"])
        nb = Notebook.load(path)
        nb.metadata["path"] = str(path)
        client, nb_ref, kernel = _make_web_client(nb)

        resp = client.get("/api/notebook/check-updates")
        assert resp.status_code == 200
        assert resp.get_json()["changed"] is False

    def test_detects_external_change(self, tmp_path):
        """check-updates returns changed=true after external file modification, reload fetches new cells."""
        path = _make_notebook_file(tmp_path, ["original"])
        nb = Notebook.load(path)
        nb.metadata["path"] = str(path)
        client, nb_ref, kernel = _make_web_client(nb)

        # Externally update the file
        nb2 = Notebook.new()
        nb2.insert_cell(0, Cell(type=CellType.CODE, source="original"))
        nb2.insert_cell(1, Cell(type=CellType.CODE, source="added_externally = 1"))
        nb2.save(path)
        _bump_mtime(path)

        # check-updates only reports change, does not reload
        resp = client.get("/api/notebook/check-updates")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["changed"] is True

        # explicit reload fetches new cells
        reload_resp = client.post("/api/notebook/reload")
        assert reload_resp.status_code == 200
        reload_data = reload_resp.get_json()
        assert "cells" in reload_data
        assert "metadata" in reload_data
        sources = [c["source"] for c in reload_data["cells"]]
        assert "added_externally = 1" in sources

    def test_no_change_when_no_path_set(self):
        """check-updates returns changed=false when notebook has no file path."""
        nb = Notebook.new()
        client, nb_ref, kernel = _make_web_client(nb)

        resp = client.get("/api/notebook/check-updates")
        data = resp.get_json()
        assert data["changed"] is False

    def test_second_check_after_reload_returns_no_change(self, tmp_path):
        """After detecting a change and reloading, next check returns changed=false."""
        path = _make_notebook_file(tmp_path, ["v1"])
        nb = Notebook.load(path)
        nb.metadata["path"] = str(path)
        client, nb_ref, kernel = _make_web_client(nb)

        nb2 = Notebook.new()
        nb2.insert_cell(0, Cell(type=CellType.CODE, source="v2"))
        nb2.save(path)
        _bump_mtime(path)

        first = client.get("/api/notebook/check-updates").get_json()
        assert first["changed"] is True

        # Explicit reload updates mtime tracking
        client.post("/api/notebook/reload")

        second = client.get("/api/notebook/check-updates").get_json()
        assert second["changed"] is False

    def test_acknowledge_resets_change_detection(self, tmp_path):
        """After acknowledging, next check returns changed=false without reloading."""
        path = _make_notebook_file(tmp_path, ["v1"])
        nb = Notebook.load(path)
        nb.metadata["path"] = str(path)
        client, nb_ref, kernel = _make_web_client(nb)

        nb2 = Notebook.new()
        nb2.insert_cell(0, Cell(type=CellType.CODE, source="v2"))
        nb2.save(path)
        _bump_mtime(path)

        first = client.get("/api/notebook/check-updates").get_json()
        assert first["changed"] is True

        # Acknowledge without reload (keep mine)
        ack = client.post("/api/notebook/acknowledge").get_json()
        assert ack["acknowledged"] is True

        second = client.get("/api/notebook/check-updates").get_json()
        assert second["changed"] is False


# ---------------------------------------------------------------------------
# Web Server – auto-save on cell mutations
# ---------------------------------------------------------------------------

class TestWebAutoSave:
    def test_auto_save_on_cell_add(self, tmp_path):
        """POST /api/cell/add saves the new cell to disk when a path is configured."""
        path = _make_notebook_file(tmp_path, [])
        nb = Notebook.load(path)
        nb.metadata["path"] = str(path)
        client, nb_ref, kernel = _make_web_client(nb)

        resp = client.post("/api/cell/add", json={"type": "code"})
        assert resp.status_code == 200

        assert len(Notebook.load(path).cells) == 1

    def test_auto_save_on_cell_update(self, tmp_path):
        """POST /api/cell/update saves the updated source to disk."""
        path = _make_notebook_file(tmp_path, ["original"])
        nb = Notebook.load(path)
        nb.metadata["path"] = str(path)
        client, nb_ref, kernel = _make_web_client(nb)

        resp = client.post("/api/cell/update", json={"index": 0, "source": "z = 777"})
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

        assert Notebook.load(path).cells[0].source == "z = 777"

    def test_auto_save_on_cell_delete(self, tmp_path):
        """POST /api/cell/delete saves the remaining cells to disk."""
        path = _make_notebook_file(tmp_path, ["keep", "delete_me"])
        nb = Notebook.load(path)
        nb.metadata["path"] = str(path)
        client, nb_ref, kernel = _make_web_client(nb)

        resp = client.post("/api/cell/delete", json={"index": 1})
        assert resp.status_code == 200

        saved = Notebook.load(path)
        assert len(saved.cells) == 1
        assert saved.cells[0].source == "keep"

    def test_no_auto_save_without_path(self):
        """Mutations on a notebook without a path don't raise errors or create files."""
        nb = Notebook.new()
        client, nb_ref, kernel = _make_web_client(nb)

        resp = client.post("/api/cell/add", json={"type": "code"})
        assert resp.status_code == 200
        assert len(nb_ref.cells) == 1


# ---------------------------------------------------------------------------
# Integration – MCP ↔ Web sync via shared file
# ---------------------------------------------------------------------------

class TestMcpToWebSync:
    def test_mcp_update_visible_to_web(self, tmp_path):
        """MCP update_cell_source -> file -> web server reads updated content."""
        path = _make_notebook_file(tmp_path, ["original"])

        # MCP modifies the file
        with patch.dict(os.environ, {"NOTEBOOK_LR_PATH": str(path)}):
            update_cell_source(index=0, source="synced_value = 123")

        # Verify the file on disk is updated
        assert Notebook.load(path).cells[0].source == "synced_value = 123"

        # Web server loads the same file
        nb_web = Notebook.load(path)
        nb_web.metadata["path"] = str(path)
        client, nb_ref, kernel = _make_web_client(nb_web)

        data = client.get("/api/notebook").get_json()
        assert data["cells"][0]["source"] == "synced_value = 123"

    def test_web_update_detected_by_mcp(self, tmp_path):
        """Web /api/cell/update -> file -> MCP list_cells detects the change."""
        path = _make_notebook_file(tmp_path, ["original"])

        # MCP loads the file first
        with patch.dict(os.environ, {"NOTEBOOK_LR_PATH": str(path)}):
            get_notebook()

            # Web server updates the same file via API
            nb_web = Notebook.load(path)
            nb_web.metadata["path"] = str(path)
            client, nb_ref, kernel = _make_web_client(nb_web)
            client.post("/api/cell/update", json={"index": 0, "source": "web_modified"})

            # Force mtime bump so MCP's _maybe_reload triggers
            _bump_mtime(path)

            result = list_cells()

        assert result.cells[0].source == "web_modified"
