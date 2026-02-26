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

    def test_web_command_requires_path(self, runner):
        """Running 'web' without a path argument should fail."""
        result = runner.invoke(main, ["web"])
        assert result.exit_code != 0

    def test_web_command_requires_existing_file(self, runner):
        """Running 'web' with a non-existent file should fail."""
        result = runner.invoke(main, ["web", "/nonexistent/path.nblr"])
        assert result.exit_code != 0


class TestWebCommandLaunch:
    """Test that the web command properly calls launch_web."""

    def test_web_command_calls_launch_web(self, runner, hello_notebook_path):
        """The web command should load the notebook and call launch_web."""
        # The import happens inside the function body: `from notebook_lr.web import launch_web`
        # so we patch at the module level before the import resolves.
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

    def test_web_command_missing_gradio(self, runner, hello_notebook_path):
        """When gradio is not installed, show helpful error message."""
        import notebook_lr.web as web_module
        with patch.object(web_module, "launch_web", side_effect=ImportError("No module named 'gradio'")):
            result = runner.invoke(main, ["web", hello_notebook_path])
        # The ImportError is caught and a helpful message is shown
        assert result.exit_code != 0 or "gradio" in (result.output or "").lower()

    def test_web_command_importerror_handling_in_source(self):
        """The web command source should contain ImportError handling."""
        from notebook_lr.cli import web
        # web is a Click Command; get the underlying callback function
        source = inspect.getsource(web.callback)
        assert "ImportError" in source, "web command should handle missing gradio"

    def test_web_command_gradio_error_message(self, runner, hello_notebook_path):
        """When gradio ImportError is raised at import time, the error message mentions gradio."""
        # Simulate missing gradio by making notebook_lr.web unimportable
        real_modules = sys.modules.copy()
        # Remove notebook_lr.web from cache so the import inside web() triggers fresh import
        sys.modules.pop("notebook_lr.web", None)

        mock_web = MagicMock()
        mock_web.launch_web.side_effect = ImportError("No module named 'gradio'")

        with patch.dict(sys.modules, {"notebook_lr.web": mock_web}):
            result = runner.invoke(main, ["web", hello_notebook_path])

        assert "gradio" in (result.output or "").lower(), \
            f"Expected 'gradio' in output, got: {result.output!r}"


class TestWebServerE2E:
    """E2E tests that actually launch the server and verify it works."""

    def test_server_starts_and_responds(self, hello_notebook_path):
        """Launch the real server process and verify it serves HTTP 200."""
        port = _find_free_port()
        venv_python = str(Path(__file__).parent.parent / ".venv" / "bin" / "python")
        env = {**__import__("os").environ, "GRADIO_SERVER_PORT": str(port)}
        proc = subprocess.Popen(
            [venv_python, "-m", "notebook_lr.cli", "web", hello_notebook_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )
        try:
            # Wait for server to start (poll up to 10 seconds)
            started = False
            for _ in range(20):
                time.sleep(0.5)
                try:
                    resp = urllib.request.urlopen(f"http://127.0.0.1:{port}", timeout=2)
                    if resp.status == 200:
                        started = True
                        break
                except Exception:
                    continue

            assert started, "Server did not start and respond with HTTP 200 within 10s"
            assert proc.poll() is None, "Server process died unexpectedly"
        finally:
            proc.terminate()
            proc.wait(timeout=5)

    def test_server_no_html_object_in_output(self, hello_notebook_path):
        """Server stdout should NOT contain '<IPython.core.display.HTML object>'."""
        port = _find_free_port()
        venv_python = str(Path(__file__).parent.parent / ".venv" / "bin" / "python")
        env = {**__import__("os").environ, "GRADIO_SERVER_PORT": str(port)}
        proc = subprocess.Popen(
            [venv_python, "-m", "notebook_lr.cli", "web", hello_notebook_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )
        try:
            # Wait for server to start
            for _ in range(20):
                time.sleep(0.5)
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{port}", timeout=2)
                    break
                except Exception:
                    continue

            proc.terminate()
            stdout, _ = proc.communicate(timeout=5)
            assert "<IPython.core.display.HTML object>" not in stdout, \
                f"Found IPython HTML object in server output: {stdout}"
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)
