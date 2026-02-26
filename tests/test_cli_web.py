"""CLI integration tests for the `notebook-lr web` command."""

import inspect
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from notebook_lr.cli import main


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def hello_notebook_path():
    return str(Path(__file__).parent.parent / "examples" / "hello.nblr")


def _find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


class TestWebCommandBasics:
    """Test basic CLI web command behavior."""

    def test_web_command_exists(self, runner):
        """The 'web' subcommand should be registered."""
        result = runner.invoke(main, ["web", "--help"])
        assert result.exit_code == 0
        assert "Launch web interface" in result.output

    def test_web_command_works_without_path(self, runner):
        """Running 'web' without a path should call launch_web(None)."""
        with patch("notebook_lr.web.launch_web") as mock_launch:
            mock_launch.return_value = None
            result = runner.invoke(main, ["web"])

        assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}: {result.output}"
        assert mock_launch.called, "launch_web() should be called even without a path"
        args = mock_launch.call_args
        nb = args[0][0] if args[0] else args[1].get("notebook")
        assert nb is None, "launch_web should receive None when no path given"

    def test_web_command_requires_existing_file(self, runner):
        """Running 'web' with a non-existent file should fail."""
        result = runner.invoke(main, ["web", "/nonexistent/path.nblr"])
        assert result.exit_code != 0


class TestWebCommandLaunch:
    """Test that the web command properly calls launch_web."""

    def test_web_command_calls_launch_web(self, runner, hello_notebook_path):
        """The web command should load the notebook and call launch_web."""
        with patch("notebook_lr.web.launch_web") as mock_launch:
            mock_launch.return_value = None
            result = runner.invoke(main, ["web", hello_notebook_path])

        assert mock_launch.called, "launch_web() was not called"
        args = mock_launch.call_args
        nb = args[0][0] if args[0] else args[1].get("notebook")
        assert nb is not None, "launch_web should receive a Notebook"

    def test_web_command_no_html_object_output(self, runner, hello_notebook_path):
        """Running web command should NOT produce '<IPython.core.display.HTML object>' output."""
        with patch("notebook_lr.web.launch_web") as mock_launch:
            mock_launch.return_value = None
            result = runner.invoke(main, ["web", hello_notebook_path])

        assert "<IPython.core.display.HTML object>" not in (result.output or ""), \
            "CLI output should not contain IPython HTML object repr"

    def test_web_command_missing_flask(self, runner, hello_notebook_path):
        """When flask is not installed, show helpful error message."""
        import notebook_lr.web as web_module
        with patch.object(web_module, "launch_web", side_effect=ImportError("No module named 'flask'")):
            result = runner.invoke(main, ["web", hello_notebook_path])
        # The ImportError is caught and a helpful message is shown
        assert result.exit_code != 0 or "flask" in (result.output or "").lower()

    def test_web_command_importerror_handling_in_source(self):
        """The web command source should contain ImportError handling."""
        from notebook_lr.cli import web
        source = inspect.getsource(web.callback)
        assert "ImportError" in source, "web command should handle missing flask"

    def test_web_command_flask_error_message(self, runner, hello_notebook_path):
        """When flask ImportError is raised at import time, the error message mentions flask."""
        real_modules = sys.modules.copy()
        sys.modules.pop("notebook_lr.web", None)

        mock_web = MagicMock()
        mock_web.launch_web.side_effect = ImportError("No module named 'flask'")

        with patch.dict(sys.modules, {"notebook_lr.web": mock_web}):
            result = runner.invoke(main, ["web", hello_notebook_path])

        assert "flask" in (result.output or "").lower(), \
            f"Expected 'flask' in output, got: {result.output!r}"
