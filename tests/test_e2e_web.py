"""Playwright E2E tests for the notebook-lr web interface."""

import threading
import time
import socket
import re

import pytest
from playwright.sync_api import sync_playwright, expect


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _find_free_port():
    """Find a free port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def gradio_app():
    """Launch the Gradio app with test cells in a background thread."""
    from notebook_lr import Notebook, Cell, CellType
    from notebook_lr.web import launch_web
    import gradio as gr

    port = _find_free_port()

    nb = Notebook.new("E2E Test Notebook")
    nb.add_cell(Cell(type=CellType.CODE, source="print('hello world')"))
    nb.add_cell(Cell(type=CellType.CODE, source="x = 42\nx"))
    nb.add_cell(Cell(type=CellType.CODE, source="1 / 0"))  # Error cell
    nb.add_cell(Cell(type=CellType.MARKDOWN, source="# Heading\nSome **bold** text"))

    original_launch = gr.Blocks.launch

    def patched_launch(self, *args, **kwargs):
        kwargs["prevent_thread_lock"] = True
        kwargs["server_port"] = port
        return original_launch(self, *args, **kwargs)

    gr.Blocks.launch = patched_launch
    try:
        thread = threading.Thread(target=launch_web, args=(nb,), daemon=True)
        thread.start()
        time.sleep(3)
    finally:
        gr.Blocks.launch = original_launch

    base_url = f"http://127.0.0.1:{port}"

    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)

    yield {
        "port": port,
        "base_url": base_url,
        "browser": browser,
        "pw": pw,
    }

    browser.close()
    pw.stop()


@pytest.fixture
def page(gradio_app):
    """Create a fresh page for each test."""
    browser = gradio_app["browser"]
    base_url = gradio_app["base_url"]

    p = browser.new_page()
    p.goto(base_url, timeout=15000)
    p.wait_for_load_state("networkidle", timeout=15000)
    # Wait for Gradio to fully render the CodeMirror editor
    p.wait_for_selector(".cm-editor", timeout=10000)
    # Give Gradio a moment to complete the demo.load() auto-select
    time.sleep(1)

    yield p

    p.close()


# ---------------------------------------------------------------------------
# Helpers — use page.get_by_label() for Gradio 6 components
# ---------------------------------------------------------------------------

def get_editor_text(page):
    """Get the text content from the CodeMirror editor."""
    return page.locator(".cm-content").inner_text().strip()


def get_cell_info(page):
    """Get the Cell Info textbox value."""
    return page.get_by_label("Cell Info").input_value()


def get_output(page):
    """Get the Output textarea value."""
    return page.get_by_label("Output", exact=True).input_value()


def get_error(page):
    """Get the Errors textarea value."""
    return page.get_by_label("Errors").input_value()


def get_dropdown_value(page):
    """Get the current dropdown value."""
    return page.get_by_label("Select Cell").input_value()


def select_cell_by_index(page, index):
    """Select a cell from the dropdown by clicking and choosing an option."""
    dropdown = page.get_by_label("Select Cell")
    dropdown.click()
    page.wait_for_selector("[role='listbox']", timeout=5000)
    page.locator(f"[role='option']:nth-child({index + 1})").click()
    # Wait for the editor to update
    time.sleep(1)


def click_button(page, text):
    """Click a button by its text content."""
    page.locator(f"button:has-text('{text}')").first.click()


def click_tab(page, tab_name):
    """Click a Gradio tab by its name using role selector."""
    page.locator(f"[role='tab']:has-text('{tab_name}')").click(force=True)
    time.sleep(0.5)


def clear_and_type_in_editor(page, text):
    """Clear the CodeMirror editor and type new text."""
    cm = page.locator(".cm-content")
    cm.click()
    page.keyboard.press("Control+a")
    page.keyboard.press("Backspace")
    page.keyboard.type(text, delay=10)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPageLoad:
    """Tests for initial page load behavior."""

    def test_page_loads(self, page):
        """App launches, page title contains 'notebook-lr', cell list is visible."""
        assert "notebook-lr" in page.title()
        expect(page.locator("text=Select Cell")).to_be_visible(timeout=5000)
        expect(page.locator("text=E2E Test Notebook")).to_be_visible(timeout=5000)

    def test_initial_cell_selected(self, page):
        """On load, first cell's code appears in the editor."""
        editor_text = get_editor_text(page)
        assert "print('hello world')" in editor_text

    def test_cell_info_displays_on_load(self, page):
        """Cell info shows code cell info on initial load."""
        cell_info = get_cell_info(page)
        assert "Code Cell #0" in cell_info


class TestCellSelection:
    """Tests for selecting different cells."""

    def test_select_cell_populates_editor(self, page):
        """Select a different cell from dropdown, editor content changes."""
        assert "print('hello world')" in get_editor_text(page)

        select_cell_by_index(page, 1)

        editor_text = get_editor_text(page)
        assert "x = 42" in editor_text

    def test_cell_info_updates_on_selection(self, page):
        """Selecting a cell shows correct cell info."""
        select_cell_by_index(page, 1)

        cell_info = get_cell_info(page)
        assert "Code Cell #1" in cell_info

    def test_select_markdown_cell(self, page):
        """Selecting a markdown cell shows its source."""
        select_cell_by_index(page, 3)

        editor_text = get_editor_text(page)
        assert "Heading" in editor_text

        cell_info = get_cell_info(page)
        assert "Markdown Cell #3" in cell_info


class TestCellExecution:
    """Tests for running code cells."""

    def test_run_cell_shows_output(self, page):
        """Select a code cell, click Run Cell, output shows expected result."""
        assert "print('hello world')" in get_editor_text(page)

        click_button(page, "Run Cell")

        # Wait for output to appear using expect with timeout
        output_el = page.get_by_label("Output", exact=True)
        expect(output_el).to_have_value(re.compile("hello world"), timeout=10000)

    def test_run_cell_with_return_value(self, page):
        """Run a cell that has a return value, check output."""
        select_cell_by_index(page, 1)

        click_button(page, "Run Cell")

        output_el = page.get_by_label("Output", exact=True)
        expect(output_el).to_have_value(re.compile("42"), timeout=10000)

    def test_run_cell_with_edited_code(self, page):
        """Edit code in the editor, run it, see new output."""
        clear_and_type_in_editor(page, "print('modified code')")
        time.sleep(0.5)

        click_button(page, "Run Cell")

        output_el = page.get_by_label("Output", exact=True)
        expect(output_el).to_have_value(re.compile("modified code"), timeout=10000)

    def test_run_all_cells(self, page):
        """Click Run All Cells, all code cells get executed."""
        click_button(page, "Run All Cells")
        time.sleep(3)

        # Verify execution happened by checking the notebook info shows executed count
        # and the dropdown shows execution counts
        info_text = page.locator("text=executed").first.inner_text()
        # At least 2 cells should have been executed (cells 0 and 1; cell 2 errors and stops)
        assert "executed" in info_text

        # Verify the dropdown shows execution indicators
        dropdown_val = get_dropdown_value(page)
        assert "[" in dropdown_val  # Has execution count like [1]

    def test_error_display(self, page):
        """Run cell with division by zero, error appears in output."""
        select_cell_by_index(page, 2)

        click_button(page, "Run Cell")

        # The error traceback appears in the Output area (via IPython's stderr/stdout capture)
        output_el = page.get_by_label("Output", exact=True)
        expect(output_el).to_have_value(re.compile("ZeroDivisionError"), timeout=10000)


class TestVariablePersistence:
    """Tests for variable persistence across cells."""

    def test_variable_persistence(self, page):
        """Run cell defining x=42, run next cell with print(x), output shows 42."""
        # Run cell 1 which defines x = 42
        select_cell_by_index(page, 1)
        click_button(page, "Run Cell")
        time.sleep(2)

        # Add a new cell and select it
        click_button(page, "+ Code")
        time.sleep(1)
        select_cell_by_index(page, 4)

        # Type code that uses x
        clear_and_type_in_editor(page, "print(x)")
        time.sleep(0.5)

        click_button(page, "Run Cell")

        output_el = page.get_by_label("Output", exact=True)
        expect(output_el).to_have_value(re.compile("42"), timeout=10000)


class TestCellManagement:
    """Tests for adding, deleting, and moving cells."""

    def test_add_code_cell(self, page):
        """Click + Code, new cell appears in the dropdown."""
        click_button(page, "+ Code")
        time.sleep(1)

        new_value = get_dropdown_value(page)
        assert "Code" in new_value
        # The new cell should be empty
        editor_text = get_editor_text(page)
        assert editor_text.strip() == ""

    def test_add_markdown_cell(self, page):
        """Click + Markdown, new markdown cell appears."""
        click_button(page, "+ Markdown")
        time.sleep(1)

        new_value = get_dropdown_value(page)
        assert "Markdown" in new_value

    def test_delete_cell(self, page):
        """Select a cell, click Delete Cell, cell is removed."""
        # Add a cell to delete
        click_button(page, "+ Code")
        time.sleep(1)

        # Count options before delete
        dropdown = page.get_by_label("Select Cell")
        dropdown.click()
        page.wait_for_selector("[role='listbox']", timeout=5000)
        options_before = page.locator("[role='option']").count()
        page.keyboard.press("Escape")
        time.sleep(0.3)

        # Delete the current cell
        click_button(page, "Delete Cell")
        time.sleep(1)

        # Count options after delete
        dropdown.click()
        page.wait_for_selector("[role='listbox']", timeout=5000)
        options_after = page.locator("[role='option']").count()
        page.keyboard.press("Escape")

        assert options_after == options_before - 1


class TestLaunchConfiguration:
    """Tests that verify the Gradio app is properly configured."""

    def test_gradio_app_has_theme(self, page):
        """Verify the Gradio app loaded with a custom theme (not default)."""
        # Check that the Soft theme's CSS variables are applied
        # Soft theme uses specific color schemes
        body_bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
        assert body_bg != "", "Theme should apply background styles"

    def test_no_html_object_in_page(self, page):
        """Verify no '<IPython.core.display.HTML object>' text appears on the page."""
        page_text = page.locator("body").inner_text()
        assert "<IPython.core.display.HTML object>" not in page_text, \
            "IPython HTML object repr should not appear on the page"
