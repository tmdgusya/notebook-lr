"""Pytest fixtures shared across all test modules."""

import pytest
from unittest.mock import patch

from notebook_lr import Notebook, NotebookKernel
from notebook_lr.mcp_server import _reset_notebook


@pytest.fixture(autouse=True)
def reset_mcp_state():
    """Reset the MCP server's global notebook state before each test."""
    _reset_notebook()
    yield
    _reset_notebook()


@pytest.fixture
def web_app():
    """Flask test app using real launch_web() routes, no route duplication."""
    from flask import Flask
    import notebook_lr.web as web_module

    nb = Notebook.new()
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
