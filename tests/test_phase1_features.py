"""Tests for Phase 1 Quick Wins features."""
import pytest
from unittest.mock import patch
from notebook_lr.kernel import NotebookKernel, _build_mime_bundle, ExecutionResult
from notebook_lr import Notebook, Cell, CellType


def _matplotlib_available():
    try:
        import matplotlib
        return True
    except ImportError:
        return False


class TestImageRenderingMimeBundle:
    """Tests for image/png and image/svg+xml MIME bundle support."""

    def test_build_mime_bundle_with_repr_png(self):
        """Object with _repr_png_ should include image/png in bundle."""
        class PngObj:
            def _repr_png_(self):
                return b"\x89PNG\r\n\x1a\n"

        bundle = _build_mime_bundle(PngObj())
        assert "image/png" in bundle
        assert bundle["image/png"] == b"\x89PNG\r\n\x1a\n"

    def test_build_mime_bundle_with_repr_svg(self):
        """Object with _repr_svg_ should include image/svg+xml in bundle."""
        class SvgObj:
            def _repr_svg_(self):
                return "<svg><circle r='10'/></svg>"

        bundle = _build_mime_bundle(SvgObj())
        assert "image/svg+xml" in bundle
        assert "<svg>" in bundle["image/svg+xml"]

    def test_build_mime_bundle_with_repr_latex(self):
        """Object with _repr_latex_ should include text/latex in bundle."""
        class LatexObj:
            def _repr_latex_(self):
                return "$x^2 + y^2 = z^2$"

        bundle = _build_mime_bundle(LatexObj())
        assert "text/latex" in bundle
        assert "$x^2" in bundle["text/latex"]

    def test_build_mime_bundle_with_repr_json(self):
        """Object with _repr_json_ should include application/json in bundle."""
        class JsonObj:
            def _repr_json_(self):
                return {"key": "value"}

        bundle = _build_mime_bundle(JsonObj())
        assert "application/json" in bundle
        assert bundle["application/json"] == {"key": "value"}

    def test_build_mime_bundle_png_is_returned_as_is(self):
        """_build_mime_bundle should return _repr_png_ value without modification."""
        fake_png = b"fakepngdata"

        class PngObj:
            def _repr_png_(self):
                return fake_png

        bundle = _build_mime_bundle(PngObj())
        assert bundle["image/png"] == fake_png

    def test_build_mime_bundle_text_plain_present(self):
        """text/plain must always be present in the bundle."""
        class SvgObj:
            def _repr_svg_(self):
                return "<svg/>"

        bundle = _build_mime_bundle(SvgObj())
        assert "text/plain" in bundle

    def test_build_mime_bundle_combined_image_types(self):
        """Object with both _repr_png_ and _repr_svg_ should include both."""
        class MultiObj:
            def _repr_png_(self):
                return b"png_data"

            def _repr_svg_(self):
                return "<svg/>"

        bundle = _build_mime_bundle(MultiObj())
        assert "image/png" in bundle
        assert "image/svg+xml" in bundle


class TestMatplotlibInlineBackend:
    """Tests for matplotlib inline backend configuration."""

    def test_setup_namespace_sets_notebook_flag(self):
        """_setup_namespace should set __notebook__ = True."""
        kernel = NotebookKernel()
        try:
            assert kernel.ip.user_ns.get("__notebook__") is True
        finally:
            kernel.reset()

    @pytest.mark.skipif(
        not _matplotlib_available(),
        reason="matplotlib not installed"
    )
    def test_matplotlib_backend_configured_after_init(self):
        """After NotebookKernel init, matplotlib backend should be agg or inline."""
        kernel = NotebookKernel()
        try:
            import matplotlib
            backend = matplotlib.get_backend().lower()
            assert 'agg' in backend or 'inline' in backend
        finally:
            kernel.reset()

    @pytest.mark.skipif(
        not _matplotlib_available(),
        reason="matplotlib not installed"
    )
    def test_execute_cell_reports_backend(self):
        """execute_cell with get_backend should return agg or inline."""
        kernel = NotebookKernel()
        try:
            result = kernel.execute_cell(
                "import matplotlib; print(matplotlib.get_backend())"
            )
            assert result.success
            stdout_outputs = [
                o for o in result.outputs
                if o.get("type") == "stream" and o.get("name") == "stdout"
            ]
            assert len(stdout_outputs) > 0
            backend_text = stdout_outputs[0]["text"].strip().lower()
            assert 'agg' in backend_text or 'inline' in backend_text
        finally:
            kernel.reset()


class TestExecutionResultWithDisplayObjects:
    """Tests for ExecutionResult with new output types."""

    def test_execute_cell_print_produces_stream_output(self):
        """execute_cell with print() should produce stream output."""
        kernel = NotebookKernel()
        try:
            result = kernel.execute_cell("print('hello phase1')")
            assert result.success
            stream_outputs = [o for o in result.outputs if o.get("type") == "stream"]
            assert len(stream_outputs) > 0
            assert "hello phase1" in stream_outputs[0]["text"]
        finally:
            kernel.reset()

    def test_execute_cell_with_html_display(self):
        """execute_cell with display(HTML(...)) should capture display_data outputs."""
        kernel = NotebookKernel()
        try:
            result = kernel.execute_cell(
                "from IPython.display import HTML; display(HTML('<b>test</b>'))"
            )
            assert result.success
            has_display = any(o['type'] == 'display_data' for o in result.outputs)
            assert has_display
        finally:
            kernel.reset()

    def test_execute_cell_display_data_has_data_key(self):
        """display_data outputs must contain a 'data' key."""
        kernel = NotebookKernel()
        try:
            result = kernel.execute_cell(
                "from IPython.display import HTML; display(HTML('<i>hi</i>'))"
            )
            assert result.success
            display_outputs = [o for o in result.outputs if o.get("type") == "display_data"]
            assert len(display_outputs) > 0
            assert "data" in display_outputs[0]
        finally:
            kernel.reset()

    def test_execute_cell_returns_execute_result_for_expression(self):
        """Evaluating an expression should produce execute_result output."""
        kernel = NotebookKernel()
        try:
            result = kernel.execute_cell("1 + 1")
            assert result.success
            exec_outputs = [o for o in result.outputs if o.get("type") == "execute_result"]
            assert len(exec_outputs) > 0
        finally:
            kernel.reset()

    def test_execute_cell_error_produces_error_output(self):
        """Executing code that raises should produce error output."""
        kernel = NotebookKernel()
        try:
            result = kernel.execute_cell("raise ValueError('test error')")
            assert not result.success
            error_outputs = [o for o in result.outputs if o.get("type") == "error"]
            assert len(error_outputs) > 0
            assert "ValueError" in error_outputs[0]["ename"]
        finally:
            kernel.reset()


class TestWebApiImageOutput:
    """Tests for /api/cell/execute returning image data in outputs."""

    @pytest.fixture
    def web_app(self):
        """Flask test app using real launch_web() routes."""
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

    def test_execute_cell_returns_outputs_list(self, web_app):
        """POST /api/cell/execute should return outputs list in response."""
        client, nb, kernel = web_app
        client.post("/api/cell/add", json={"type": "code"})
        data = client.post(
            "/api/cell/execute",
            json={"index": 0, "source": "print('hello')"}
        ).get_json()
        assert "outputs" in data
        assert isinstance(data["outputs"], list)

    def test_execute_cell_with_html_display_returns_display_data(self, web_app):
        """Executing display(HTML(...)) should return display_data in outputs."""
        client, nb, kernel = web_app
        client.post("/api/cell/add", json={"type": "code"})
        data = client.post(
            "/api/cell/execute",
            json={
                "index": 0,
                "source": "from IPython.display import HTML; display(HTML('<b>hi</b>'))"
            }
        ).get_json()
        assert data["success"] is True
        has_display = any(o.get("type") == "display_data" for o in data["outputs"])
        assert has_display

    def test_api_save_endpoint(self, web_app, tmp_path):
        """POST /api/save should return saved status."""
        client, nb, kernel = web_app
        nb.metadata["path"] = str(tmp_path / "test_notebook.nblr")
        resp = client.post("/api/save", json={})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "saved" in data["status"]
        assert "path" in data
