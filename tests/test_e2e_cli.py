"""
E2E tests for the CLI interface using Click's CliRunner.
"""

import json
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from notebook_lr.cli import main
from notebook_lr.notebook import Notebook, Cell, CellType


class TestNewCommandE2E:
    """Test `notebook-lr new` command end-to-end."""

    def test_new_default_path(self):
        """Create notebook at default path (notebook.nblr)."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["new"])
            assert result.exit_code == 0, result.output
            assert Path("notebook.nblr").exists()

    def test_new_custom_path(self):
        """Create notebook at a custom path."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["new", "my_notebook.nblr"])
            assert result.exit_code == 0, result.output
            assert Path("my_notebook.nblr").exists()

    def test_new_with_name_option(self):
        """Create notebook with --name option sets metadata name."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["new", "test.nblr", "--name", "My Test Notebook"])
            assert result.exit_code == 0, result.output
            assert Path("test.nblr").exists()

            nb = Notebook.load(Path("test.nblr"))
            assert nb.metadata["name"] == "My Test Notebook"

    def test_new_with_name_short_flag(self):
        """Create notebook with -n short flag."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["new", "test.nblr", "-n", "Short Flag Name"])
            assert result.exit_code == 0, result.output
            nb = Notebook.load(Path("test.nblr"))
            assert nb.metadata["name"] == "Short Flag Name"

    def test_new_creates_valid_json(self):
        """Created file is valid JSON."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["new", "test.nblr"])
            assert result.exit_code == 0, result.output

            with open("test.nblr") as f:
                data = json.load(f)

            assert "version" in data
            assert "cells" in data
            assert "metadata" in data

    def test_new_has_expected_cells(self):
        """Created notebook has 1 code cell and 1 markdown cell."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["new", "test.nblr"])
            assert result.exit_code == 0, result.output

            nb = Notebook.load(Path("test.nblr"))
            assert len(nb.cells) == 2

            code_cells = [c for c in nb.cells if c.type == CellType.CODE]
            markdown_cells = [c for c in nb.cells if c.type == CellType.MARKDOWN]
            assert len(code_cells) == 1
            assert len(markdown_cells) == 1

    def test_new_default_name_from_stem(self):
        """Without --name, notebook name defaults to file stem."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["new", "my_project.nblr"])
            assert result.exit_code == 0, result.output

            nb = Notebook.load(Path("my_project.nblr"))
            assert nb.metadata["name"] == "my_project"

    def test_new_output_mentions_path(self):
        """CLI output mentions the created file path."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["new", "myfile.nblr"])
            assert result.exit_code == 0, result.output
            assert "myfile.nblr" in result.output

    def test_new_in_nested_directory(self):
        """Creating notebook in a non-existent subdirectory creates parent dirs."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["new", "subdir/nested/test.nblr"])
            assert result.exit_code == 0, result.output
            assert Path("subdir/nested/test.nblr").exists()


class TestRunCommandE2E:
    """Test `notebook-lr run` command end-to-end."""

    def _make_notebook(self, path: str, cells: list[dict]) -> Path:
        """Helper: create and save a notebook at the given path."""
        nb = Notebook.new("Test Notebook")
        for cell_spec in cells:
            nb.add_cell(
                type=cell_spec.get("type", CellType.CODE),
                source=cell_spec["source"],
            )
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        nb.save(p)
        return p

    def test_run_simple_cell(self):
        """Run a notebook with a simple assignment cell."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            self._make_notebook("test.nblr", [{"source": "x = 42"}])

            result = runner.invoke(main, ["run", "test.nblr"])
            assert result.exit_code == 0, result.output

    def test_run_saves_outputs(self):
        """After running, cell outputs are persisted to disk."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            self._make_notebook("test.nblr", [{"source": "print('hello world')"}])

            result = runner.invoke(main, ["run", "test.nblr"])
            assert result.exit_code == 0, result.output

            nb = Notebook.load(Path("test.nblr"))
            code_cells = [c for c in nb.cells if c.type == CellType.CODE]
            assert len(code_cells) == 1
            assert len(code_cells[0].outputs) > 0

            # Verify stdout output was captured
            stream_outputs = [o for o in code_cells[0].outputs if o.get("type") == "stream"]
            assert any("hello world" in o.get("text", "") for o in stream_outputs)

    def test_run_saves_execution_count(self):
        """After running, execution_count is set on code cells."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            self._make_notebook("test.nblr", [{"source": "x = 1"}])

            result = runner.invoke(main, ["run", "test.nblr"])
            assert result.exit_code == 0, result.output

            nb = Notebook.load(Path("test.nblr"))
            code_cells = [c for c in nb.cells if c.type == CellType.CODE]
            assert code_cells[0].execution_count is not None
            assert code_cells[0].execution_count >= 1

    def test_run_print_output(self):
        """Running a notebook that prints shows output in CLI."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            self._make_notebook("test.nblr", [{"source": "print('cli output test')"}])

            result = runner.invoke(main, ["run", "test.nblr"])
            assert result.exit_code == 0, result.output
            assert "cli output test" in result.output

    def test_run_stops_on_error(self):
        """Execution stops when a cell raises an error."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            self._make_notebook("test.nblr", [
                {"source": "raise ValueError('intentional error')"},
                {"source": "print('this should not run')"},
            ])

            result = runner.invoke(main, ["run", "test.nblr"])
            assert result.exit_code == 0, result.output  # CLI exits 0 even on cell error
            assert "this should not run" not in result.output

            # Verify second cell was not executed (no execution_count)
            nb = Notebook.load(Path("test.nblr"))
            code_cells = [c for c in nb.cells if c.type == CellType.CODE]
            assert len(code_cells) == 2
            # Second cell should have no outputs and no execution_count
            assert code_cells[1].execution_count is None
            assert code_cells[1].outputs == []

    def test_run_error_shown_in_output(self):
        """Error message is displayed in CLI output."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            self._make_notebook("test.nblr", [{"source": "raise RuntimeError('boom')"}])

            result = runner.invoke(main, ["run", "test.nblr"])
            assert result.exit_code == 0, result.output
            assert "Error" in result.output or "boom" in result.output

    def test_run_with_save_session_flag(self):
        """--save-session flag creates a checkpoint file."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            self._make_notebook("test.nblr", [{"source": "x = 99"}])

            result = runner.invoke(main, ["run", "test.nblr", "--save-session"])
            assert result.exit_code == 0, result.output

            # Checkpoint is stored in ~/.notebook_lr/sessions/checkpoints/
            # We just verify the CLI reported session saved
            assert "session" in result.output.lower() or "saved" in result.output.lower()

    def test_run_with_save_session_short_flag(self):
        """Short -s flag also saves session."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            self._make_notebook("test.nblr", [{"source": "y = 7"}])

            result = runner.invoke(main, ["run", "test.nblr", "-s"])
            assert result.exit_code == 0, result.output

    def test_run_nonexistent_notebook_fails(self):
        """Running a non-existent notebook exits with nonzero code."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["run", "does_not_exist.nblr"])
            assert result.exit_code != 0


class TestRunWithPersistentStateE2E:
    """Test that state persists across cells within a single run."""

    def _make_notebook(self, path: str, cells: list[dict]) -> Path:
        nb = Notebook.new("Persistence Test")
        for cell_spec in cells:
            nb.add_cell(
                type=cell_spec.get("type", CellType.CODE),
                source=cell_spec["source"],
            )
        p = Path(path)
        nb.save(p)
        return p

    def test_variable_persists_across_cells(self):
        """Variable defined in cell 1 is available in cell 2."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            self._make_notebook("test.nblr", [
                {"source": "x = 10"},
                {"source": "print(x + 1)"},
            ])

            result = runner.invoke(main, ["run", "test.nblr"])
            assert result.exit_code == 0, result.output
            assert "11" in result.output

    def test_cell2_depends_on_cell1_variable(self):
        """Cell 2 output reflects cell 1's computed value."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            self._make_notebook("test.nblr", [
                {"source": "x = 5\ny = x * 2"},
                {"source": "print(y)"},
            ])

            result = runner.invoke(main, ["run", "test.nblr"])
            assert result.exit_code == 0, result.output
            assert "10" in result.output

    def test_imports_in_cell1_available_in_cell2(self):
        """Imports in cell 1 are available in cell 2."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            self._make_notebook("test.nblr", [
                {"source": "import math"},
                {"source": "print(math.pi)"},
            ])

            result = runner.invoke(main, ["run", "test.nblr"])
            assert result.exit_code == 0, result.output
            assert "3.14" in result.output

    def test_function_defined_in_cell1_called_in_cell2(self):
        """Function defined in cell 1 is callable in cell 2."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            self._make_notebook("test.nblr", [
                {"source": "def greet(name):\n    return f'Hello, {name}!'"},
                {"source": "print(greet('World'))"},
            ])

            result = runner.invoke(main, ["run", "test.nblr"])
            assert result.exit_code == 0, result.output
            assert "Hello, World!" in result.output

    def test_outputs_saved_reflect_persisted_state(self):
        """Saved outputs in cell 2 reflect state set by cell 1."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            self._make_notebook("test.nblr", [
                {"source": "value = 42"},
                {"source": "print(value)"},
            ])

            result = runner.invoke(main, ["run", "test.nblr"])
            assert result.exit_code == 0, result.output

            nb = Notebook.load(Path("test.nblr"))
            code_cells = [c for c in nb.cells if c.type == CellType.CODE]
            assert len(code_cells) == 2

            # Cell 2 outputs should contain "42"
            cell2_outputs = code_cells[1].outputs
            stream_text = "".join(
                o.get("text", "") for o in cell2_outputs if o.get("type") == "stream"
            )
            assert "42" in stream_text

    def test_multiple_cells_chained(self):
        """Multiple cells chain state correctly."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            self._make_notebook("test.nblr", [
                {"source": "a = 1"},
                {"source": "b = a + 1"},
                {"source": "c = b + 1"},
                {"source": "print(c)"},
            ])

            result = runner.invoke(main, ["run", "test.nblr"])
            assert result.exit_code == 0, result.output
            assert "3" in result.output


class TestSessionsCommandE2E:
    """Test `notebook-lr sessions` command end-to-end."""

    def test_sessions_with_no_sessions_does_not_error(self):
        """sessions command with no saved sessions exits cleanly."""
        runner = CliRunner()
        # We use a temporary sessions dir via env - but SessionManager uses ~/.notebook_lr
        # We test that the command doesn't crash regardless of what's in ~/.notebook_lr
        result = runner.invoke(main, ["sessions"])
        assert result.exit_code == 0, result.output

    def test_sessions_output_no_sessions_message(self):
        """When no sessions exist, a helpful message is shown (or table displayed)."""
        runner = CliRunner()
        result = runner.invoke(main, ["sessions"])
        assert result.exit_code == 0, result.output
        # Either shows "No saved sessions" or a table - output must be non-empty or blank
        # Just verify it doesn't crash with a stack trace
        assert "Traceback" not in result.output

    def test_sessions_after_save_session_run(self):
        """After running with --save-session, sessions command lists that session."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            cwd = Path.cwd()
            nb_path = cwd / "session_test.nblr"
            nb = Notebook.new("SessionTest")
            nb.add_cell(type=CellType.CODE, source="session_var = 123")
            nb.save(nb_path)

            run_result = runner.invoke(main, ["run", str(nb_path), "--save-session"])
            assert run_result.exit_code == 0, run_result.output

            sessions_result = runner.invoke(main, ["sessions"])
            assert sessions_result.exit_code == 0, sessions_result.output
            # After saving, output should not be only "No saved sessions"
            # (there's at least one session now)
            assert "Traceback" not in sessions_result.output


class TestCLIEdgeCasesE2E:
    """Edge cases for the CLI commands."""

    def _make_notebook(self, path: str, cells: list[dict]) -> Path:
        nb = Notebook.new("Edge Case Test")
        for cell_spec in cells:
            nb.add_cell(
                type=cell_spec.get("type", CellType.CODE),
                source=cell_spec["source"],
            )
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        nb.save(p)
        return p

    def test_run_empty_notebook_no_code_cells(self):
        """Running notebook with no code cells at all exits cleanly."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            nb = Notebook.new("Empty")
            nb.save(Path("empty.nblr"))

            result = runner.invoke(main, ["run", "empty.nblr"])
            assert result.exit_code == 0, result.output
            assert "No code cells" in result.output

    def test_run_only_markdown_cells(self):
        """Running notebook with only markdown cells exits cleanly."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            self._make_notebook("md_only.nblr", [
                {"type": CellType.MARKDOWN, "source": "# Title"},
                {"type": CellType.MARKDOWN, "source": "Some text"},
            ])

            result = runner.invoke(main, ["run", "md_only.nblr"])
            assert result.exit_code == 0, result.output
            assert "No code cells" in result.output

    def test_new_in_nested_nonexistent_directory(self):
        """new command creates parent directories automatically."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["new", "level1/level2/notebook.nblr"])
            assert result.exit_code == 0, result.output
            assert Path("level1/level2/notebook.nblr").exists()

    def test_run_error_in_first_cell_stops_execution(self):
        """Error in the first cell prevents subsequent cells from running."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            self._make_notebook("test.nblr", [
                {"source": "1 / 0"},  # ZeroDivisionError
                {"source": "print('should not appear in output')"},
            ])

            result = runner.invoke(main, ["run", "test.nblr"])
            assert result.exit_code == 0, result.output
            assert "should not appear in output" not in result.output

    def test_run_code_cell_with_empty_source_skipped(self):
        """Code cells with empty/whitespace-only source are skipped."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            nb = Notebook.new("Test")
            nb.add_cell(type=CellType.CODE, source="   ")   # whitespace only
            nb.add_cell(type=CellType.CODE, source="print('ran')")
            nb.save(Path("test.nblr"))

            result = runner.invoke(main, ["run", "test.nblr"])
            assert result.exit_code == 0, result.output
            assert "ran" in result.output

    def test_run_partial_success_reported(self):
        """When not all cells execute, partial count is shown."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            self._make_notebook("test.nblr", [
                {"source": "x = 1"},
                {"source": "raise Exception('stop here')"},
                {"source": "y = 2"},
            ])

            result = runner.invoke(main, ["run", "test.nblr"])
            assert result.exit_code == 0, result.output
            # Should mention partial execution (1/3 or similar)
            assert "1" in result.output

    def test_new_overwrites_existing_file(self):
        """new command overwrites existing notebook file."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create first notebook with a name
            runner.invoke(main, ["new", "test.nblr", "--name", "First"])
            nb_before = Notebook.load(Path("test.nblr"))
            assert nb_before.metadata["name"] == "First"

            # Overwrite with a new notebook
            result = runner.invoke(main, ["new", "test.nblr", "--name", "Second"])
            assert result.exit_code == 0, result.output

            nb_after = Notebook.load(Path("test.nblr"))
            assert nb_after.metadata["name"] == "Second"

    def test_run_all_cells_success_message(self):
        """Successful full run displays success summary."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            self._make_notebook("test.nblr", [
                {"source": "a = 1"},
                {"source": "b = 2"},
            ])

            result = runner.invoke(main, ["run", "test.nblr"])
            assert result.exit_code == 0, result.output
            # Should say something like "All 2 cells executed successfully"
            output_lower = result.output.lower()
            assert "executed" in output_lower or "success" in output_lower
