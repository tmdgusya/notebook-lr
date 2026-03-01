"""Tests for Mermaid diagram rendering support.

Verifies that mermaid.js is properly integrated into the notebook web interface
for rendering diagrams in markdown cell preview mode and execution outputs.
"""
import pytest
import os
from pathlib import Path
from notebook_lr import Notebook, Cell, CellType


# ---------------------------------------------------------------------------
# Template integration tests
# ---------------------------------------------------------------------------

class TestMermaidTemplateIntegration:
    """Verify mermaid.js is properly included in the HTML template."""

    def _read_template(self):
        template_path = os.path.join(
            os.path.dirname(__file__),
            "..", "notebook_lr", "templates", "notebook.html"
        )
        with open(template_path) as f:
            return f.read()

    def test_mermaid_cdn_script_present(self):
        """Template should include mermaid.js CDN script tag."""
        html = self._read_template()
        assert "mermaid" in html
        assert "cdn.jsdelivr.net/npm/mermaid" in html

    def test_mermaid_script_not_deferred(self):
        """Mermaid script should NOT be deferred (needed at render time)."""
        html = self._read_template()
        # Find the mermaid script line
        for line in html.splitlines():
            if "cdn.jsdelivr.net/npm/mermaid" in line and "<script" in line:
                assert "defer" not in line, "Mermaid script should not be deferred"
                break
        else:
            pytest.fail("Mermaid CDN script tag not found")

    def test_mermaid_initialization_present(self):
        """Template should initialize mermaid with startOnLoad: false."""
        html = self._read_template()
        assert "mermaid.initialize" in html
        assert "startOnLoad" in html

    def test_mermaid_security_level_strict(self):
        """Mermaid should be initialized with securityLevel: 'strict'."""
        html = self._read_template()
        assert "securityLevel" in html
        assert "'strict'" in html or '"strict"' in html

    def test_mermaid_script_before_app_js(self):
        """Mermaid CDN should be loaded before application JS files."""
        html = self._read_template()
        mermaid_pos = html.find("cdn.jsdelivr.net/npm/mermaid")
        app_js_pos = html.find("static/js/cells.js")
        assert mermaid_pos > 0, "Mermaid CDN not found"
        assert app_js_pos > 0, "cells.js not found"
        assert mermaid_pos < app_js_pos, (
            "Mermaid CDN must be loaded before cells.js"
        )

    def test_mermaid_loaded_after_dompurify(self):
        """Mermaid should be loaded after DOMPurify for security."""
        html = self._read_template()
        purify_pos = html.find("dompurify")
        mermaid_pos = html.find("cdn.jsdelivr.net/npm/mermaid")
        assert purify_pos < mermaid_pos, (
            "DOMPurify should be loaded before mermaid"
        )


# ---------------------------------------------------------------------------
# JavaScript source tests - cells.js
# ---------------------------------------------------------------------------

class TestMermaidCellsJs:
    """Verify cells.js has proper mermaid rendering support."""

    def _read_cells_js(self):
        js_path = os.path.join(
            os.path.dirname(__file__),
            "..", "notebook_lr", "static", "js", "cells.js"
        )
        with open(js_path) as f:
            return f.read()

    def test_render_mermaid_function_exists(self):
        """cells.js should define a renderMermaid function."""
        js = self._read_cells_js()
        assert "function renderMermaid" in js

    def test_render_mermaid_checks_mermaid_availability(self):
        """renderMermaid should check if mermaid library is loaded."""
        js = self._read_cells_js()
        assert "typeof mermaid" in js

    def test_render_mermaid_selects_language_mermaid(self):
        """renderMermaid should select code blocks with language-mermaid class."""
        js = self._read_cells_js()
        assert "language-mermaid" in js

    def test_render_mermaid_uses_mermaid_run(self):
        """renderMermaid should use mermaid.run() (v11 API)."""
        js = self._read_cells_js()
        assert "mermaid.run(" in js

    def test_render_mermaid_called_in_preview_button(self):
        """renderMermaid should be called in the preview button click handler."""
        js = self._read_cells_js()
        # Find the preview button handler section (contains renderKaTeX and renderMermaid)
        # Both renderKaTeX and renderMermaid should appear close together
        katex_calls = [i for i, line in enumerate(js.splitlines())
                       if "renderKaTeX(previewEl)" in line]
        mermaid_calls = [i for i, line in enumerate(js.splitlines())
                         if "renderMermaid(previewEl)" in line]
        assert len(katex_calls) >= 2, (
            "renderKaTeX(previewEl) should be called at least twice "
            "(preview button + onExitEdit)"
        )
        assert len(mermaid_calls) >= 2, (
            "renderMermaid(previewEl) should be called at least twice "
            "(preview button + onExitEdit)"
        )

    def test_render_mermaid_has_error_handling(self):
        """renderMermaid should have try/catch for error handling."""
        js = self._read_cells_js()
        # Find the renderMermaid function and check for try/catch
        func_start = js.find("function renderMermaid")
        assert func_start >= 0
        # Look for try/catch within a reasonable range after the function definition
        func_section = js[func_start:func_start + 600]
        assert "try" in func_section and "catch" in func_section


# ---------------------------------------------------------------------------
# JavaScript source tests - execution.js
# ---------------------------------------------------------------------------

class TestMermaidExecutionJs:
    """Verify execution.js handles mermaid in markdown outputs."""

    def _read_execution_js(self):
        js_path = os.path.join(
            os.path.dirname(__file__),
            "..", "notebook_lr", "static", "js", "execution.js"
        )
        with open(js_path) as f:
            return f.read()

    def test_execution_js_has_mermaid_rendering(self):
        """execution.js should render mermaid blocks in markdown output."""
        js = self._read_execution_js()
        assert "language-mermaid" in js

    def test_execution_js_mermaid_in_markdown_handler(self):
        """Mermaid rendering should be in the text/markdown handler."""
        js = self._read_execution_js()
        # Find the text/markdown handler
        md_start = js.find("text/markdown")
        assert md_start >= 0
        # Find mermaid handling after the markdown handler
        mermaid_pos = js.find("mermaid", md_start)
        # Find the next else-if branch (image/png)
        next_branch = js.find("image/png", md_start)
        assert md_start < mermaid_pos < next_branch, (
            "Mermaid rendering should be within the text/markdown handler block"
        )

    def test_execution_js_uses_mermaid_run(self):
        """execution.js should use mermaid.run() for rendering."""
        js = self._read_execution_js()
        assert "mermaid.run(" in js

    def test_execution_js_mermaid_error_handling(self):
        """execution.js mermaid rendering should have error handling."""
        js = self._read_execution_js()
        # Find mermaid.run and verify try/catch surrounds it
        run_pos = js.find("mermaid.run(")
        assert run_pos >= 0
        # Look backwards for try
        section_before = js[max(0, run_pos - 200):run_pos]
        assert "try" in section_before


# ---------------------------------------------------------------------------
# CSS tests
# ---------------------------------------------------------------------------

class TestMermaidCss:
    """Verify CSS styles for mermaid diagrams."""

    def _read_css(self):
        css_path = os.path.join(
            os.path.dirname(__file__),
            "..", "notebook_lr", "static", "css", "notebook.css"
        )
        with open(css_path) as f:
            return f.read()

    def test_mermaid_preview_styles_exist(self):
        """CSS should have styles for mermaid in preview mode."""
        css = self._read_css()
        assert ".cell-md-preview .mermaid" in css

    def test_mermaid_output_styles_exist(self):
        """CSS should have styles for mermaid in cell output."""
        css = self._read_css()
        assert ".cell-output .mermaid" in css

    def test_mermaid_centered(self):
        """Mermaid diagrams should be centered."""
        css = self._read_css()
        assert "justify-content: center" in css

    def test_mermaid_svg_responsive(self):
        """Mermaid SVG should be responsive (max-width: 100%)."""
        css = self._read_css()
        # Check for SVG styling within mermaid context
        assert ".mermaid svg" in css
        assert "max-width: 100%" in css


# ---------------------------------------------------------------------------
# Web endpoint tests
# ---------------------------------------------------------------------------

class TestMermaidWebEndpoint:
    """Verify the served web page includes mermaid support."""

    def test_index_page_contains_mermaid_script(self, web_app):
        """GET / should serve HTML with mermaid.js included."""
        client, nb, kernel = web_app
        resp = client.get("/")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "mermaid" in html
        assert "cdn.jsdelivr.net/npm/mermaid" in html

    def test_index_page_has_mermaid_init(self, web_app):
        """GET / should serve HTML with mermaid initialization."""
        client, nb, kernel = web_app
        resp = client.get("/")
        html = resp.data.decode("utf-8")
        assert "mermaid.initialize" in html

    def test_markdown_cell_with_mermaid_source_preserved(self, web_app):
        """Markdown cell with mermaid code block should preserve source."""
        client, nb, kernel = web_app
        mermaid_source = "```mermaid\ngraph TD\n    A-->B\n```"
        resp = client.post(
            "/api/cell/add",
            json={"type": "markdown"}
        )
        assert resp.status_code == 200

        resp = client.post(
            "/api/cell/update",
            json={"index": 0, "source": mermaid_source}
        )
        assert resp.status_code == 200

        nb_data = client.get("/api/notebook").get_json()
        assert nb_data["cells"][0]["source"] == mermaid_source
        assert nb_data["cells"][0]["type"] == "markdown"


# ---------------------------------------------------------------------------
# Notebook model tests
# ---------------------------------------------------------------------------

class TestMermaidNotebookModel:
    """Verify notebook model handles mermaid content correctly."""

    def test_markdown_cell_stores_mermaid_source(self):
        """Markdown cell should store mermaid code blocks in source."""
        mermaid_src = "```mermaid\nsequenceDiagram\n    A->>B: Hello\n```"
        cell = Cell(type=CellType.MARKDOWN, source=mermaid_src)
        assert cell.source == mermaid_src
        assert cell.type == CellType.MARKDOWN

    def test_notebook_serialization_preserves_mermaid(self, tmp_path):
        """Saving and loading notebook should preserve mermaid content."""
        mermaid_src = "```mermaid\ngraph LR\n    A-->B\n    B-->C\n```"
        nb = Notebook.new("Mermaid Test")
        nb.add_cell(Cell(type=CellType.MARKDOWN, source=mermaid_src))

        path = tmp_path / "mermaid_test.nblr"
        nb.save(Path(path))

        loaded = Notebook.load(Path(path))
        assert len(loaded.cells) == 1
        assert loaded.cells[0].source == mermaid_src
        assert loaded.cells[0].type == CellType.MARKDOWN

    def test_notebook_multiple_mermaid_cells(self):
        """Notebook should handle multiple markdown cells with mermaid."""
        nb = Notebook.new()
        diagrams = [
            "```mermaid\ngraph TD\n    A-->B\n```",
            "```mermaid\nsequenceDiagram\n    Alice->>Bob: Hi\n```",
            "```mermaid\npie\n    title Pets\n    \"Dogs\" : 386\n    \"Cats\" : 85\n```",
        ]
        for src in diagrams:
            nb.add_cell(Cell(type=CellType.MARKDOWN, source=src))

        assert len(nb.cells) == 3
        for i, src in enumerate(diagrams):
            assert nb.cells[i].source == src

    def test_mixed_markdown_and_mermaid(self):
        """Cell with mixed markdown text and mermaid blocks should be stored."""
        mixed_src = (
            "# Architecture\n\n"
            "Below is the system diagram:\n\n"
            "```mermaid\ngraph TD\n    A[Web] --> B[API]\n    B --> C[DB]\n```\n\n"
            "And here is the sequence:\n\n"
            "```mermaid\nsequenceDiagram\n    User->>API: Request\n```"
        )
        cell = Cell(type=CellType.MARKDOWN, source=mixed_src)
        assert "# Architecture" in cell.source
        assert "graph TD" in cell.source
        assert "sequenceDiagram" in cell.source


# ---------------------------------------------------------------------------
# Markdown default preview mode tests
# ---------------------------------------------------------------------------

class TestMarkdownDefaultPreviewMode:
    """Verify markdown cells default to preview mode when they have content."""

    def _read_cells_js(self):
        js_path = os.path.join(
            os.path.dirname(__file__),
            "..", "notebook_lr", "static", "js", "cells.js"
        )
        with open(js_path) as f:
            return f.read()

    def test_default_preview_logic_exists(self):
        """cells.js should have logic to default markdown cells to preview."""
        js = self._read_cells_js()
        assert "default to preview mode" in js.lower() or \
               "default to preview" in js.lower(), \
            "cells.js should have a comment about defaulting to preview mode"

    def test_default_preview_checks_content(self):
        """Default preview should only activate when cell has content."""
        js = self._read_cells_js()
        # Should check value is non-empty before activating preview
        assert "value.trim().length > 0" in js or \
               "value.trim()" in js, \
            "Should check that cell content is non-empty before preview"

    def test_default_preview_sets_preview_active(self):
        """Default preview should set previewActive = true."""
        js = self._read_cells_js()
        # Find the default preview section
        default_pos = js.find("default to preview")
        assert default_pos >= 0, "Default preview comment not found"
        section = js[default_pos:default_pos + 500]
        assert "previewActive = true" in section

    def test_default_preview_shows_preview_hides_editor(self):
        """Default preview should show previewEl and hide editorEl."""
        js = self._read_cells_js()
        default_pos = js.find("default to preview")
        assert default_pos >= 0
        section = js[default_pos:default_pos + 500]
        assert "previewEl.style.display = ''" in section
        assert "editorEl.style.display = 'none'" in section

    def test_default_preview_renders_markdown(self):
        """Default preview should parse markdown with marked."""
        js = self._read_cells_js()
        default_pos = js.find("default to preview")
        assert default_pos >= 0
        section = js[default_pos:default_pos + 500]
        assert "marked.parse" in section

    def test_default_preview_renders_katex_and_mermaid(self):
        """Default preview should call renderKaTeX and renderMermaid."""
        js = self._read_cells_js()
        default_pos = js.find("default to preview")
        assert default_pos >= 0
        section = js[default_pos:default_pos + 500]
        assert "renderKaTeX" in section
        assert "renderMermaid" in section

    def test_default_preview_updates_button_text(self):
        """Default preview should set button text to 'Edit'."""
        js = self._read_cells_js()
        default_pos = js.find("default to preview")
        assert default_pos >= 0
        section = js[default_pos:default_pos + 500]
        assert "'Edit'" in section or '"Edit"' in section

    def test_empty_markdown_cell_stays_in_edit_mode(self):
        """Empty markdown cells should NOT default to preview mode."""
        js = self._read_cells_js()
        # The condition checks value.trim().length > 0, so empty cells stay in edit
        assert "value.trim().length > 0" in js, \
            "Should only preview non-empty markdown cells"
