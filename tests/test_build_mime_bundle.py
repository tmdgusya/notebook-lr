"""
Unit tests for the _build_mime_bundle function in notebook_lr.kernel.
"""

import pytest
from notebook_lr.kernel import _build_mime_bundle


class TestBuildMimeBundlePlainObjects:
    """Tests for plain Python objects with no rich display methods."""

    def test_plain_string_uses_repr(self):
        result = _build_mime_bundle("hello")
        assert "text/plain" in result
        assert result["text/plain"] == repr("hello")

    def test_plain_int_uses_repr(self):
        result = _build_mime_bundle(42)
        assert result["text/plain"] == repr(42)

    def test_plain_list_uses_repr(self):
        obj = [1, 2, 3]
        result = _build_mime_bundle(obj)
        assert result["text/plain"] == repr(obj)

    def test_plain_dict_uses_repr(self):
        obj = {"a": 1}
        result = _build_mime_bundle(obj)
        assert result["text/plain"] == repr(obj)

    def test_plain_none_uses_repr(self):
        result = _build_mime_bundle(None)
        assert result["text/plain"] == repr(None)

    def test_no_extra_mime_keys_for_plain_object(self):
        result = _build_mime_bundle(42)
        assert set(result.keys()) == {"text/plain"}


class TestBuildMimeBundleHtmlMethod:
    """Tests for objects with _repr_html_ method."""

    def test_html_key_present(self):
        class HtmlObj:
            def _repr_html_(self):
                return "<b>bold</b>"

        result = _build_mime_bundle(HtmlObj())
        assert "text/html" in result
        assert result["text/html"] == "<b>bold</b>"

    def test_plain_uses_html_content_not_repr(self):
        class HtmlObj:
            def _repr_html_(self):
                return "<b>bold</b>"

        result = _build_mime_bundle(HtmlObj())
        # text/plain should be the HTML content, not repr(obj)
        assert result["text/plain"] == "<b>bold</b>"
        assert "<HtmlObj" not in result["text/plain"]

    def test_html_method_returns_none_is_skipped(self):
        class HtmlObj:
            def _repr_html_(self):
                return None

        result = _build_mime_bundle(HtmlObj())
        assert "text/html" not in result
        # Falls back to repr since no rich content
        assert "text/plain" in result

    def test_non_callable_html_attr_is_ignored(self):
        class HtmlObj:
            _repr_html_ = "<b>not callable</b>"

        result = _build_mime_bundle(HtmlObj())
        assert "text/html" not in result


class TestBuildMimeBundleMarkdownMethod:
    """Tests for objects with _repr_markdown_ method."""

    def test_markdown_key_present(self):
        class MdObj:
            def _repr_markdown_(self):
                return "**bold**"

        result = _build_mime_bundle(MdObj())
        assert "text/markdown" in result
        assert result["text/markdown"] == "**bold**"

    def test_plain_uses_markdown_as_fallback(self):
        class MdObj:
            def _repr_markdown_(self):
                return "**bold**"

        result = _build_mime_bundle(MdObj())
        assert result["text/plain"] == "**bold**"

    def test_markdown_returns_none_is_skipped(self):
        class MdObj:
            def _repr_markdown_(self):
                return None

        result = _build_mime_bundle(MdObj())
        assert "text/markdown" not in result


class TestBuildMimeBundleJsonMethod:
    """Tests for objects with _repr_json_ method."""

    def test_json_key_present(self):
        class JsonObj:
            def _repr_json_(self):
                return {"key": "value"}

        result = _build_mime_bundle(JsonObj())
        assert "application/json" in result
        assert result["application/json"] == {"key": "value"}

    def test_plain_uses_json_as_fallback(self):
        class JsonObj:
            def _repr_json_(self):
                return {"key": "value"}

        result = _build_mime_bundle(JsonObj())
        assert result["text/plain"] == {"key": "value"}


class TestBuildMimeBundleLatexMethod:
    """Tests for objects with _repr_latex_ method."""

    def test_latex_key_present(self):
        class LatexObj:
            def _repr_latex_(self):
                return r"$x^2$"

        result = _build_mime_bundle(LatexObj())
        assert "text/latex" in result
        assert result["text/latex"] == r"$x^2$"

    def test_plain_uses_latex_as_fallback(self):
        class LatexObj:
            def _repr_latex_(self):
                return r"$x^2$"

        result = _build_mime_bundle(LatexObj())
        assert result["text/plain"] == r"$x^2$"


class TestBuildMimeBundleSvgMethod:
    """Tests for objects with _repr_svg_ method."""

    def test_svg_key_present(self):
        class SvgObj:
            def _repr_svg_(self):
                return "<svg></svg>"

        result = _build_mime_bundle(SvgObj())
        assert "image/svg+xml" in result
        assert result["image/svg+xml"] == "<svg></svg>"


class TestBuildMimeBundlePngMethod:
    """Tests for objects with _repr_png_ method."""

    def test_png_key_present(self):
        class PngObj:
            def _repr_png_(self):
                return b"\x89PNG..."

        result = _build_mime_bundle(PngObj())
        assert "image/png" in result
        assert result["image/png"] == b"\x89PNG..."


class TestBuildMimeBundlePriority:
    """Tests for mime type priority and multi-method objects."""

    def test_html_takes_priority_over_markdown_for_plain(self):
        """_repr_html_ is checked first; text/plain should be the HTML content."""
        class MultiObj:
            def _repr_html_(self):
                return "<b>html</b>"

            def _repr_markdown_(self):
                return "**md**"

        result = _build_mime_bundle(MultiObj())
        # HTML is listed first so rich_content = HTML value
        assert result["text/plain"] == "<b>html</b>"
        assert "text/html" in result
        assert "text/markdown" in result

    def test_multiple_mime_types_all_present(self):
        class MultiObj:
            def _repr_html_(self):
                return "<b>html</b>"

            def _repr_markdown_(self):
                return "**md**"

            def _repr_json_(self):
                return {"k": "v"}

        result = _build_mime_bundle(MultiObj())
        assert "text/html" in result
        assert "text/markdown" in result
        assert "application/json" in result
        assert "text/plain" in result

    def test_always_has_text_plain_key(self):
        class Empty:
            pass

        result = _build_mime_bundle(Empty())
        assert "text/plain" in result

    def test_result_is_dict(self):
        result = _build_mime_bundle(42)
        assert isinstance(result, dict)

    def test_all_expected_mime_types_supported(self):
        """Verify all six MIME types the function handles are actually handled."""
        class AllMethods:
            def _repr_html_(self): return "<b>h</b>"
            def _repr_markdown_(self): return "**m**"
            def _repr_json_(self): return {}
            def _repr_latex_(self): return r"$x$"
            def _repr_svg_(self): return "<svg/>"
            def _repr_png_(self): return b"png"

        result = _build_mime_bundle(AllMethods())
        expected_types = {
            "text/plain",
            "text/html",
            "text/markdown",
            "application/json",
            "text/latex",
            "image/svg+xml",
            "image/png",
        }
        assert set(result.keys()) == expected_types


class TestBuildMimeBundleIpythonDisplayObjects:
    """Integration-style tests using actual IPython display objects."""

    def test_ipython_html_object(self):
        from IPython.display import HTML
        result = _build_mime_bundle(HTML("<h1>hi</h1>"))
        assert "text/html" in result
        assert "<h1>hi</h1>" in result["text/html"]
        assert "<IPython.core.display.HTML object>" not in result["text/plain"]

    def test_ipython_markdown_object(self):
        from IPython.display import Markdown
        result = _build_mime_bundle(Markdown("**bold**"))
        assert "text/markdown" in result
        assert "**bold**" in result["text/markdown"]

    def test_ipython_json_object(self):
        from IPython.display import JSON
        result = _build_mime_bundle(JSON({"a": 1}))
        assert "application/json" in result

    def test_ipython_latex_object(self):
        from IPython.display import Latex
        result = _build_mime_bundle(Latex(r"$x^2$"))
        assert "text/latex" in result
        assert r"$x^2$" in result["text/latex"]
