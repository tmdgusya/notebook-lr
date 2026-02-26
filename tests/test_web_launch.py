"""Tests for web launch behavior - verifies Flask backend is configured correctly."""

import inspect
from unittest.mock import patch, MagicMock

from notebook_lr import Notebook


class TestFlaskLaunchConfiguration:
    """Verify Flask app is configured correctly."""

    def test_import_works(self):
        """Web module should be importable."""
        import notebook_lr.web
        assert hasattr(notebook_lr.web, "launch_web")

    def test_launch_web_signature(self):
        """launch_web() should accept notebook and share parameters."""
        from notebook_lr.web import launch_web
        sig = inspect.signature(launch_web)
        assert "notebook" in sig.parameters
        assert "share" in sig.parameters

    def test_launch_web_uses_flask(self):
        """launch_web() source should import flask, not gradio."""
        from notebook_lr.web import launch_web
        source = inspect.getsource(launch_web)
        assert "flask" in source.lower(), "launch_web should use Flask"
        assert "gradio" not in source.lower(), "launch_web should not use Gradio"

    def test_launch_web_creates_api_routes(self):
        """launch_web() source should define REST API routes."""
        from notebook_lr.web import launch_web
        source = inspect.getsource(launch_web)
        assert "/api/notebook" in source
        assert "/api/cell/add" in source
        assert "/api/cell/execute" in source
        assert "/api/cell/delete" in source
        assert "/api/variables" in source

    def test_launch_web_serves_template(self):
        """launch_web() should serve notebook.html template."""
        from notebook_lr.web import launch_web
        source = inspect.getsource(launch_web)
        assert "notebook.html" in source
        assert "render_template" in source
