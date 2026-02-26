"""Tests for web launch behavior - verifies Gradio is configured correctly.

In Gradio 6.x, theme and css parameters belong on launch(), not Blocks().
The critical fix is inline=False to prevent IPython HTML object display.
"""

import importlib
from unittest.mock import patch, MagicMock


def _make_gradio_mock():
    """Create a fully mocked gradio module that records Blocks/launch kwargs."""
    gr_mock = MagicMock()

    # Make themes work
    gr_mock.themes.Soft.return_value = MagicMock(name="SoftTheme")

    # Make Blocks() context manager return a demo mock
    demo_mock = MagicMock()
    demo_mock.__enter__ = MagicMock(return_value=demo_mock)
    demo_mock.__exit__ = MagicMock(return_value=False)
    demo_mock.launch.return_value = (None, "http://127.0.0.1:7860", None)

    # gr.Blocks(...) -> demo_mock
    gr_mock.Blocks.return_value = demo_mock

    # All component constructors return mocks that act as context managers
    for component in [
        "Row", "Column", "Tabs", "Tab", "Accordion",
        "Markdown", "Dropdown", "Button", "Code",
        "Textbox", "TextArea", "File",
    ]:
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=cm)
        cm.__exit__ = MagicMock(return_value=False)
        getattr(gr_mock, component).return_value = cm

    # gr.update() returns a dict-like mock
    gr_mock.update.return_value = {}

    return gr_mock, demo_mock


class TestGradioLaunchConfiguration:
    """Verify demo.launch() is called with correct parameters (Gradio 6.x API)."""

    def test_launch_has_inline_false(self):
        """demo.launch() must use inline=False to prevent IPython HTML display."""
        gr_mock, demo_mock = _make_gradio_mock()

        with patch.dict("sys.modules", {"gradio": gr_mock}):
            import notebook_lr.web
            importlib.reload(notebook_lr.web)
            notebook_lr.web.launch_web()

        assert demo_mock.launch.called, "demo.launch() must be called"
        _, kwargs = demo_mock.launch.call_args
        assert kwargs.get("inline") is False, \
            "launch() must use inline=False to prevent IPython HTML object display"

    def test_launch_has_theme(self):
        """demo.launch() should receive theme parameter (Gradio 6.x API)."""
        gr_mock, demo_mock = _make_gradio_mock()

        with patch.dict("sys.modules", {"gradio": gr_mock}):
            import notebook_lr.web
            importlib.reload(notebook_lr.web)
            notebook_lr.web.launch_web()

        assert demo_mock.launch.called, "demo.launch() must be called"
        _, kwargs = demo_mock.launch.call_args
        assert "theme" in kwargs, \
            "launch() must receive theme parameter (Gradio 6.x API)"
        assert kwargs["theme"] is not None

    def test_launch_has_css(self):
        """demo.launch() should receive css parameter (Gradio 6.x API)."""
        gr_mock, demo_mock = _make_gradio_mock()

        with patch.dict("sys.modules", {"gradio": gr_mock}):
            import notebook_lr.web
            importlib.reload(notebook_lr.web)
            notebook_lr.web.launch_web()

        assert demo_mock.launch.called, "demo.launch() must be called"
        _, kwargs = demo_mock.launch.call_args
        assert "css" in kwargs, \
            "launch() must receive css parameter (Gradio 6.x API)"
        assert kwargs["css"] is not None
        assert len(kwargs["css"]) > 0

    def test_launch_uses_soft_theme(self):
        """demo.launch() theme should come from gr.themes.Soft()."""
        gr_mock, demo_mock = _make_gradio_mock()

        with patch.dict("sys.modules", {"gradio": gr_mock}):
            import notebook_lr.web
            importlib.reload(notebook_lr.web)
            notebook_lr.web.launch_web()

        # gr.themes.Soft() should have been called
        assert gr_mock.themes.Soft.called, "gr.themes.Soft() must be called for theme"

    def test_launch_is_called_once(self):
        """demo.launch() must be called exactly once."""
        gr_mock, demo_mock = _make_gradio_mock()

        with patch.dict("sys.modules", {"gradio": gr_mock}):
            import notebook_lr.web
            importlib.reload(notebook_lr.web)
            notebook_lr.web.launch_web()

        assert demo_mock.launch.call_count == 1, \
            "demo.launch() must be called exactly once"


class TestBlocksConfiguration:
    """Verify gr.Blocks() constructor has correct parameters."""

    def test_blocks_has_title(self):
        """gr.Blocks() should receive title='notebook-lr'."""
        gr_mock, demo_mock = _make_gradio_mock()

        with patch.dict("sys.modules", {"gradio": gr_mock}):
            import notebook_lr.web
            importlib.reload(notebook_lr.web)
            notebook_lr.web.launch_web()

        assert gr_mock.Blocks.called, "gr.Blocks() must be called"
        _, kwargs = gr_mock.Blocks.call_args
        assert kwargs.get("title") == "notebook-lr", \
            "gr.Blocks() must receive title='notebook-lr'"

    def test_blocks_no_theme_in_gradio6(self):
        """gr.Blocks() should NOT receive theme (moved to launch() in Gradio 6)."""
        gr_mock, demo_mock = _make_gradio_mock()

        with patch.dict("sys.modules", {"gradio": gr_mock}):
            import notebook_lr.web
            importlib.reload(notebook_lr.web)
            notebook_lr.web.launch_web()

        assert gr_mock.Blocks.called, "gr.Blocks() must be called"
        _, kwargs = gr_mock.Blocks.call_args
        assert "theme" not in kwargs, \
            "theme should be on launch(), not gr.Blocks() in Gradio 6.x"

    def test_blocks_no_css_in_gradio6(self):
        """gr.Blocks() should NOT receive css (moved to launch() in Gradio 6)."""
        gr_mock, demo_mock = _make_gradio_mock()

        with patch.dict("sys.modules", {"gradio": gr_mock}):
            import notebook_lr.web
            importlib.reload(notebook_lr.web)
            notebook_lr.web.launch_web()

        assert gr_mock.Blocks.called, "gr.Blocks() must be called"
        _, kwargs = gr_mock.Blocks.call_args
        assert "css" not in kwargs, \
            "css should be on launch(), not gr.Blocks() in Gradio 6.x"
