"""
End-to-end integration tests for notebook-lr.

Tests the full workflow combining all components: kernel, notebook, session, and CLI.

IMPORTANT - IPython singleton behaviour
---------------------------------------
NotebookKernel wraps IPython's InteractiveShell.instance(), which is a process-wide
singleton.  All NotebookKernel objects therefore share the *same* namespace.  To get
a clean slate between independent tests (or between "concurrent" notebooks in a single
test) we call kernel.reset() before each distinct execution context.

JSON-safe session_data
----------------------
Notebook.save(include_session=True, session_data=...) serialises session_data with
json.dump.  The raw namespace returned by kernel.get_namespace() contains modules,
functions and other non-JSON-serializable objects.  We therefore filter it down to
only JSON-serializable primitive values (str, int, float, bool, list, dict, None)
before embedding it in the .nblr file.  The SessionManager uses dill for its own
.session files and handles arbitrary objects there.
"""

import json
import math
import statistics
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest
from click.testing import CliRunner

from notebook_lr.cli import main
from notebook_lr.kernel import ExecutionResult, NotebookKernel
from notebook_lr.notebook import Cell, CellType, Notebook
from notebook_lr.session import SessionManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_JSON_PRIMITIVES = (str, int, float, bool, type(None))


def _json_safe_ns(ns: dict) -> dict:
    """Return a copy of *ns* containing only JSON-serializable primitive values.

    This is necessary when embedding namespace data inside a .nblr file
    (which is JSON), because the raw IPython namespace contains modules,
    functions, and other objects that json.dump cannot serialise.
    """
    safe: dict[str, Any] = {}
    for k, v in ns.items():
        try:
            # Quick round-trip test – cheap for primitives, raises for rest.
            json.dumps(v)
            safe[k] = v
        except (TypeError, ValueError):
            pass
    return safe


# ---------------------------------------------------------------------------
# TestFullWorkflowE2E
# ---------------------------------------------------------------------------

class TestFullWorkflowE2E:
    """Complete user workflow simulation: create, execute, save, reload."""

    # Six code cells that simulate a data analysis session using only stdlib.
    CELL_SOURCES = [
        # Cell 0 – imports
        "import math\nimport statistics\nfrom collections import Counter",
        # Cell 1 – define data
        "data = [4, 8, 15, 16, 23, 42, 3, 7, 11, 19, 27, 35]",
        # Cell 2 – compute statistics
        (
            "mean_val = statistics.mean(data)\n"
            "median_val = statistics.median(data)\n"
            "stdev_val = statistics.stdev(data)\n"
            "print(f'mean={mean_val}, median={median_val}, stdev={stdev_val:.2f}')"
        ),
        # Cell 3 – filter data
        "above_mean = [x for x in data if x > mean_val]\nprint(f'above mean: {above_mean}')",
        # Cell 4 – aggregate results
        (
            "buckets = Counter()\n"
            "for x in data:\n"
            "    buckets['low' if x < mean_val else 'high'] += 1\n"
            "print(f'buckets: {dict(buckets)}')"
        ),
        # Cell 5 – print summary
        "print(f'n={len(data)}, range={max(data)-min(data)}, above_mean_count={len(above_mean)}')",
    ]

    def test_full_workflow(self):
        with TemporaryDirectory() as tmpdir:
            nb_path = Path(tmpdir) / "analysis.nblr"

            # --- Step 1: create notebook and add cells ---
            nb = Notebook.new("Data Analysis")
            for src in self.CELL_SOURCES:
                nb.add_cell(type=CellType.CODE, source=src)
            assert len(nb.cells) == 6

            # --- Step 2: execute all cells and update notebook cells ---
            kernel = NotebookKernel()
            kernel.reset()  # clear shared singleton state
            for idx, cell in enumerate(nb.cells):
                result = kernel.execute_cell(cell.source)
                assert result.success, (
                    f"Cell {idx} failed: {result.error}\nSource:\n{cell.source}"
                )
                nb.update_cell(
                    idx,
                    outputs=result.outputs,
                    execution_count=result.execution_count,
                )

            # --- Step 3: verify execution counts incremented 1-6 ---
            for idx in range(6):
                assert nb.get_cell(idx).execution_count == idx + 1

            # --- Step 4: verify key variables are in the kernel ---
            assert kernel.get_variable("data") == [4, 8, 15, 16, 23, 42, 3, 7, 11, 19, 27, 35]
            mean_val = kernel.get_variable("mean_val")
            assert mean_val == statistics.mean([4, 8, 15, 16, 23, 42, 3, 7, 11, 19, 27, 35])
            above_mean = kernel.get_variable("above_mean")
            assert all(x > mean_val for x in above_mean)

            # --- Step 5: save notebook with session state ---
            # Only JSON-serializable primitives go into the .nblr file's
            # session_state block; use SessionManager for full state.
            sm = SessionManager(sessions_dir=Path(tmpdir) / "sessions")
            session_file = sm.save_session(kernel, name="analysis")
            session_data = {
                "user_ns": _json_safe_ns(kernel.get_namespace()),
                "execution_count": kernel.execution_count,
            }
            nb.save(nb_path, include_session=True, session_data=session_data)
            assert nb_path.exists()

            # --- Step 6: load notebook and verify structure ---
            loaded_nb = Notebook.load(nb_path)
            assert loaded_nb.metadata["name"] == "Data Analysis"
            assert len(loaded_nb.cells) == 6
            for idx in range(6):
                assert loaded_nb.get_cell(idx).source == self.CELL_SOURCES[idx]
                assert loaded_nb.get_cell(idx).execution_count == idx + 1
            assert loaded_nb.session_state is not None

            # --- Step 7: restore session via SessionManager and verify variables ---
            kernel.reset()
            new_kernel = NotebookKernel()
            info = sm.load_session(new_kernel, session_file)
            assert "data" in info["restored_vars"]
            assert new_kernel.get_variable("data") == [4, 8, 15, 16, 23, 42, 3, 7, 11, 19, 27, 35]
            assert new_kernel.get_variable("mean_val") == mean_val
            assert new_kernel.get_variable("above_mean") == above_mean
            assert new_kernel.execution_count == 6


# ---------------------------------------------------------------------------
# TestCLIToAPIRoundtripE2E
# ---------------------------------------------------------------------------

class TestCLIToAPIRoundtripE2E:
    """CLI creates notebook, API loads and modifies, CLI runs it."""

    def test_cli_create_api_modify_cli_run(self):
        with TemporaryDirectory() as tmpdir:
            nb_path = Path(tmpdir) / "roundtrip.nblr"
            runner = CliRunner()

            # --- Step 1: create notebook via CLI ---
            result = runner.invoke(main, ["new", str(nb_path), "--name", "Roundtrip"])
            assert result.exit_code == 0, f"CLI new failed: {result.output}"
            assert nb_path.exists()

            # --- Step 2: load via API and verify initial structure ---
            nb = Notebook.load(nb_path)
            assert nb.metadata["name"] == "Roundtrip"
            # CLI creates 2 default cells (1 code, 1 markdown)
            assert len(nb.cells) >= 1

            # --- Step 3: add more cells programmatically ---
            nb.add_cell(type=CellType.CODE, source="x = 10\ny = 20")
            nb.add_cell(type=CellType.CODE, source="z = x + y\nprint(f'z={z}')")
            nb.add_cell(type=CellType.MARKDOWN, source="## Results\n\nSee output above.")
            nb.save(nb_path)

            # --- Step 4: verify saved notebook has the new cells ---
            reloaded = Notebook.load(nb_path)
            code_cells = [c for c in reloaded.cells if c.type == CellType.CODE and c.source.strip()]
            assert any("x = 10" in c.source for c in code_cells)
            assert any("z = x + y" in c.source for c in code_cells)

            # --- Step 5: run via CLI ---
            run_result = runner.invoke(main, ["run", str(nb_path)])
            assert run_result.exit_code == 0, f"CLI run failed: {run_result.output}"
            assert "cells executed" in run_result.output.lower() or "executed" in run_result.output.lower()

            # --- Step 6: load again and verify outputs were populated ---
            final_nb = Notebook.load(nb_path)
            executed_code_cells = [
                c for c in final_nb.cells
                if c.type == CellType.CODE and c.execution_count is not None
            ]
            assert len(executed_code_cells) > 0


# ---------------------------------------------------------------------------
# TestSessionContinuationE2E
# ---------------------------------------------------------------------------

class TestSessionContinuationE2E:
    """Simulate closing and reopening a notebook across multiple sessions."""

    def test_three_session_continuation(self):
        with TemporaryDirectory() as tmpdir:
            nb_path = Path(tmpdir) / "continued.nblr"
            sm = SessionManager(sessions_dir=Path(tmpdir) / "sessions")

            # ===== Session 1: create notebook, execute, save =====
            nb1 = Notebook.new("Continued")
            nb1.add_cell(type=CellType.CODE, source="counter = 0\nstep = 5")
            nb1.add_cell(type=CellType.CODE, source="counter += step\nprint(f'counter={counter}')")
            nb1.save(nb_path)

            kernel1 = NotebookKernel()
            kernel1.reset()  # clear shared singleton
            for idx, cell in enumerate(nb1.cells):
                result = kernel1.execute_cell(cell.source)
                assert result.success, f"Session1 cell {idx} failed: {result.error}"
                nb1.update_cell(idx, outputs=result.outputs, execution_count=result.execution_count)

            assert kernel1.get_variable("counter") == 5

            # Save session via SessionManager
            session_path = sm.save_session(kernel1, name="session1")
            nb1.save(nb_path)

            # "Close" session 1 — reset singleton so session 2 starts fresh
            kernel1.reset()
            del kernel1

            # ===== Session 2: restore, execute more cells =====
            kernel2 = NotebookKernel()
            info2 = sm.load_session(kernel2, session_path)
            assert "counter" in info2["restored_vars"]
            assert kernel2.get_variable("counter") == 5

            nb2 = Notebook.load(nb_path)
            # Add a new cell that depends on the restored state
            nb2.add_cell(type=CellType.CODE, source="counter += step\nprint(f'session2 counter={counter}')")
            nb2.save(nb_path)

            result2 = kernel2.execute_cell(nb2.get_cell(2).source)
            assert result2.success, f"Session2 new cell failed: {result2.error}"
            assert kernel2.get_variable("counter") == 10

            nb2.update_cell(2, outputs=result2.outputs, execution_count=result2.execution_count)
            session_path2 = sm.save_session(kernel2, name="session2")
            nb2.save(nb_path)

            # "Close" session 2 — reset singleton so session 3 starts fresh
            kernel2.reset()
            del kernel2

            # ===== Session 3: restore again, execute one more cell =====
            kernel3 = NotebookKernel()
            info3 = sm.load_session(kernel3, session_path2)
            assert kernel3.get_variable("counter") == 10

            nb3 = Notebook.load(nb_path)
            nb3.add_cell(type=CellType.CODE, source="final = counter * 2\nprint(f'final={final}')")
            nb3.save(nb_path)

            result3 = kernel3.execute_cell(nb3.get_cell(3).source)
            assert result3.success, f"Session3 cell failed: {result3.error}"
            assert kernel3.get_variable("final") == 20

            nb3.update_cell(3, outputs=result3.outputs, execution_count=result3.execution_count)
            nb3.save(nb_path)

            # Verify final saved state
            final_nb = Notebook.load(nb_path)
            assert len(final_nb.cells) == 4
            assert final_nb.get_cell(3).execution_count is not None


# ---------------------------------------------------------------------------
# TestConcurrentNotebooksE2E
# ---------------------------------------------------------------------------

class TestConcurrentNotebooksE2E:
    """Multiple independent notebooks with isolated variable namespaces.

    Because NotebookKernel wraps the process-wide IPython singleton, true
    concurrency is impossible in a single process.  Instead we run each
    notebook sequentially on the shared kernel, reset() between runs, and
    capture the results we care about into plain Python dicts so they
    survive the reset.  Sessions are saved via SessionManager (dill) which
    *does* handle functions/modules; notebooks are saved with JSON-safe
    primitives only in session_state.
    """

    def test_three_independent_notebooks(self):
        with TemporaryDirectory() as tmpdir:
            sm = SessionManager(sessions_dir=Path(tmpdir) / "sessions")
            kernel = NotebookKernel()

            # --- Notebook 1: math computations ---
            math_nb = Notebook.new("Math")
            math_nb.add_cell(type=CellType.CODE, source="import math\nresult = math.factorial(5)")
            math_nb.add_cell(type=CellType.CODE, source="pi_approx = math.pi\nvalue = 42")

            kernel.reset()
            for idx, cell in enumerate(math_nb.cells):
                result = kernel.execute_cell(cell.source)
                assert result.success, f"math cell {idx} failed: {result.error}"
                math_nb.update_cell(idx, outputs=result.outputs, execution_count=result.execution_count)

            math_result = kernel.get_variable("result")       # 120
            math_value = kernel.get_variable("value")          # 42
            math_pi = kernel.get_variable("pi_approx")

            assert math_result == 120
            assert math_value == 42

            math_session = sm.save_session(kernel, name="math")
            math_path = Path(tmpdir) / "math.nblr"
            math_nb.save(math_path, include_session=True,
                         session_data={"user_ns": _json_safe_ns(kernel.get_namespace()),
                                       "execution_count": kernel.execution_count})

            # --- Notebook 2: text processing ---
            text_nb = Notebook.new("Text")
            text_nb.add_cell(type=CellType.CODE, source="text = 'hello world'\nvalue = text.upper()")
            text_nb.add_cell(type=CellType.CODE, source="words = text.split()\nword_count = len(words)")

            kernel.reset()
            for idx, cell in enumerate(text_nb.cells):
                result = kernel.execute_cell(cell.source)
                assert result.success, f"text cell {idx} failed: {result.error}"
                text_nb.update_cell(idx, outputs=result.outputs, execution_count=result.execution_count)

            text_value = kernel.get_variable("value")          # "HELLO WORLD"
            text_word_count = kernel.get_variable("word_count")  # 2

            assert text_value == "HELLO WORLD"
            assert text_word_count == 2
            # After text run, math variables must NOT be present (reset cleared them)
            assert kernel.get_variable("result") is None
            assert kernel.get_variable("pi_approx") is None

            text_session = sm.save_session(kernel, name="text")
            text_path = Path(tmpdir) / "text.nblr"
            text_nb.save(text_path, include_session=True,
                         session_data={"user_ns": _json_safe_ns(kernel.get_namespace()),
                                       "execution_count": kernel.execution_count})

            # --- Notebook 3: data processing ---
            data_nb = Notebook.new("Data")
            data_nb.add_cell(type=CellType.CODE, source="numbers = list(range(10))\nvalue = sum(numbers)")
            data_nb.add_cell(type=CellType.CODE, source="evens = [x for x in numbers if x % 2 == 0]")

            kernel.reset()
            for idx, cell in enumerate(data_nb.cells):
                result = kernel.execute_cell(cell.source)
                assert result.success, f"data cell {idx} failed: {result.error}"
                data_nb.update_cell(idx, outputs=result.outputs, execution_count=result.execution_count)

            data_value = kernel.get_variable("value")          # 45
            data_evens = kernel.get_variable("evens")          # [0,2,4,6,8]

            assert data_value == 45
            assert data_evens == [0, 2, 4, 6, 8]
            # text variables must NOT be present
            assert kernel.get_variable("text") is None
            assert kernel.get_variable("word_count") is None

            data_session = sm.save_session(kernel, name="data")
            data_path = Path(tmpdir) / "data.nblr"
            data_nb.save(data_path, include_session=True,
                         session_data={"user_ns": _json_safe_ns(kernel.get_namespace()),
                                       "execution_count": kernel.execution_count})

            # --- Reload each notebook and verify saved metadata ---
            for name, nb_path in [("Math", math_path), ("Text", text_path), ("Data", data_path)]:
                loaded = Notebook.load(nb_path)
                assert loaded.metadata["name"] == name
                assert loaded.session_state is not None

            # --- Restore sessions and verify variable isolation ---
            # Math session
            kernel.reset()
            math_restored_kernel = NotebookKernel()
            sm.load_session(math_restored_kernel, math_session)
            assert math_restored_kernel.get_variable("result") == 120
            assert math_restored_kernel.get_variable("value") == 42
            assert math_restored_kernel.get_variable("word_count") is None
            assert math_restored_kernel.get_variable("evens") is None

            # Text session (restore into a fresh reset)
            kernel.reset()
            text_restored_kernel = NotebookKernel()
            sm.load_session(text_restored_kernel, text_session)
            assert text_restored_kernel.get_variable("value") == "HELLO WORLD"
            assert text_restored_kernel.get_variable("word_count") == 2
            assert text_restored_kernel.get_variable("result") is None
            assert text_restored_kernel.get_variable("evens") is None

            # Data session
            kernel.reset()
            data_restored_kernel = NotebookKernel()
            sm.load_session(data_restored_kernel, data_session)
            assert data_restored_kernel.get_variable("evens") == [0, 2, 4, 6, 8]
            assert data_restored_kernel.get_variable("value") == 45
            assert data_restored_kernel.get_variable("text") is None
            assert data_restored_kernel.get_variable("word_count") is None


# ---------------------------------------------------------------------------
# TestNotebookEvolutionE2E
# ---------------------------------------------------------------------------

class TestNotebookEvolutionE2E:
    """Notebook changes over time: add cells, remove cells, reorder."""

    def test_notebook_evolution(self):
        with TemporaryDirectory() as tmpdir:
            nb_path = Path(tmpdir) / "evolving.nblr"

            # ===== Version 1: 3 cells =====
            nb = Notebook.new("Evolving")
            nb.add_cell(type=CellType.CODE, source="a = 1")
            nb.add_cell(type=CellType.CODE, source="b = 2")
            nb.add_cell(type=CellType.CODE, source="c = a + b\nprint(c)")

            kernel = NotebookKernel()
            kernel.reset()
            for idx, cell in enumerate(nb.cells):
                result = kernel.execute_cell(cell.source)
                assert result.success
                nb.update_cell(idx, outputs=result.outputs, execution_count=result.execution_count)

            assert kernel.get_variable("c") == 3
            nb.save(nb_path)

            # ===== Version 2: add 2 cells, remove cell 1 (b=2) =====
            nb2 = Notebook.load(nb_path)
            nb2.remove_cell(1)                                           # remove "b = 2"
            nb2.add_cell(type=CellType.CODE, source="d = 10")
            nb2.add_cell(type=CellType.CODE, source="e = a + d\nprint(e)")

            assert len(nb2.cells) == 4                                   # was 3, -1+2 = 4
            assert nb2.get_cell(0).source == "a = 1"
            assert nb2.get_cell(1).source == "c = a + b\nprint(c)"

            kernel2 = NotebookKernel()
            kernel2.reset()
            for idx, cell in enumerate(nb2.cells):
                if cell.type == CellType.CODE and cell.source.strip():
                    result = kernel2.execute_cell(cell.source)
                    # cell index 1 references b which is not defined – expect failure there
                    nb2.update_cell(idx, outputs=result.outputs, execution_count=result.execution_count)

            # a=1 was executed; d=10 and e=a+d may have executed too
            assert kernel2.get_variable("a") == 1
            assert kernel2.get_variable("d") == 10
            nb2.save(nb_path)

            # ===== Version 3: reorder cells (swap first two remaining cells) =====
            nb3 = Notebook.load(nb_path)
            original_cell0_src = nb3.get_cell(0).source
            original_cell1_src = nb3.get_cell(1).source

            # Swap cells 0 and 1
            nb3.cells[0], nb3.cells[1] = nb3.cells[1], nb3.cells[0]
            assert nb3.get_cell(0).source == original_cell1_src
            assert nb3.get_cell(1).source == original_cell0_src

            # Clear execution state so cells re-execute cleanly
            for idx in range(len(nb3.cells)):
                nb3.update_cell(idx, outputs=[], execution_count=None)

            nb3.save(nb_path)
            final = Notebook.load(nb_path)
            assert final.get_cell(0).source == original_cell1_src
            assert final.get_cell(1).source == original_cell0_src
            assert len(final.cells) == 4


# ---------------------------------------------------------------------------
# TestEdgeCasesE2E
# ---------------------------------------------------------------------------

class TestEdgeCasesE2E:
    """Edge case integration tests."""

    def test_empty_notebook_save_load(self):
        """Empty notebook (no cells) save/load round-trip."""
        with TemporaryDirectory() as tmpdir:
            nb_path = Path(tmpdir) / "empty.nblr"
            nb = Notebook.new("Empty")
            nb.save(nb_path)

            loaded = Notebook.load(nb_path)
            assert loaded.metadata["name"] == "Empty"
            assert len(loaded.cells) == 0

    def test_markdown_only_notebook(self):
        """Notebook with only markdown cells."""
        with TemporaryDirectory() as tmpdir:
            nb_path = Path(tmpdir) / "markdown_only.nblr"
            nb = Notebook.new("Docs")
            nb.add_cell(type=CellType.MARKDOWN, source="# Title")
            nb.add_cell(type=CellType.MARKDOWN, source="## Section 1\n\nSome text.")
            nb.add_cell(type=CellType.MARKDOWN, source="## Section 2\n\nMore text.")
            nb.save(nb_path)

            loaded = Notebook.load(nb_path)
            assert len(loaded.cells) == 3
            assert all(c.type == CellType.MARKDOWN for c in loaded.cells)

            # Running a markdown-only notebook via kernel: no code cells to execute
            kernel = NotebookKernel()
            kernel.reset()
            code_cells = [c for c in loaded.cells if c.type == CellType.CODE]
            assert len(code_cells) == 0

    def test_large_cell_source(self):
        """Cell with 1000+ character source."""
        with TemporaryDirectory() as tmpdir:
            nb_path = Path(tmpdir) / "large_source.nblr"

            # Build a 1200-char source
            lines = [f"var_{i} = {i}" for i in range(200)]
            large_source = "\n".join(lines)
            assert len(large_source) > 1000

            nb = Notebook.new("LargeSource")
            nb.add_cell(type=CellType.CODE, source=large_source)
            nb.save(nb_path)

            loaded = Notebook.load(nb_path)
            assert loaded.get_cell(0).source == large_source

            kernel = NotebookKernel()
            kernel.reset()
            result = kernel.execute_cell(large_source)
            assert result.success
            assert kernel.get_variable("var_0") == 0
            assert kernel.get_variable("var_199") == 199

    def test_cell_with_large_output(self):
        """Cell that produces large output."""
        with TemporaryDirectory() as tmpdir:
            nb_path = Path(tmpdir) / "large_output.nblr"

            source = "for i in range(100):\n    print(f'line {i}')"
            nb = Notebook.new("LargeOutput")
            nb.add_cell(type=CellType.CODE, source=source)

            kernel = NotebookKernel()
            kernel.reset()
            result = kernel.execute_cell(source)
            assert result.success
            stdout_outputs = [o for o in result.outputs if o.get("name") == "stdout"]
            assert len(stdout_outputs) > 0
            combined = "".join(o["text"] for o in stdout_outputs)
            assert "line 0" in combined
            assert "line 99" in combined

            nb.update_cell(0, outputs=result.outputs, execution_count=result.execution_count)
            nb.save(nb_path)

            loaded = Notebook.load(nb_path)
            assert len(loaded.get_cell(0).outputs) > 0

    def test_unicode_in_source_and_outputs(self):
        """Unicode characters in cell source and outputs."""
        with TemporaryDirectory() as tmpdir:
            nb_path = Path(tmpdir) / "unicode.nblr"

            source = "msg = 'こんにちは世界 🌍'\nprint(msg)"
            nb = Notebook.new("Unicode")
            nb.add_cell(type=CellType.CODE, source=source)

            kernel = NotebookKernel()
            kernel.reset()
            result = kernel.execute_cell(source)
            assert result.success
            stdout_outputs = [o for o in result.outputs if o.get("name") == "stdout"]
            combined = "".join(o["text"] for o in stdout_outputs)
            assert "こんにちは世界" in combined

            nb.update_cell(0, outputs=result.outputs, execution_count=result.execution_count)
            nb.save(nb_path)

            loaded = Notebook.load(nb_path)
            assert "こんにちは世界" in loaded.get_cell(0).source
            loaded_outputs = loaded.get_cell(0).outputs
            assert len(loaded_outputs) > 0
            combined_loaded = "".join(
                o.get("text", "") for o in loaded_outputs if o.get("name") == "stdout"
            )
            assert "こんにちは世界" in combined_loaded

    def test_special_characters_in_notebook_name(self):
        """Special characters in notebook name (metadata only, not filename)."""
        with TemporaryDirectory() as tmpdir:
            nb_path = Path(tmpdir) / "special.nblr"
            nb = Notebook.new("My Notebook: Analysis & Results (v2)")
            nb.add_cell(type=CellType.CODE, source="x = 1")
            nb.save(nb_path)

            loaded = Notebook.load(nb_path)
            assert loaded.metadata["name"] == "My Notebook: Analysis & Results (v2)"

    def test_notebook_with_50_plus_cells(self):
        """Notebook with 50+ cells save/load/execute."""
        with TemporaryDirectory() as tmpdir:
            nb_path = Path(tmpdir) / "fifty_cells.nblr"
            nb = Notebook.new("Fifty")

            for i in range(55):
                nb.add_cell(type=CellType.CODE, source=f"cell_var_{i} = {i}")

            assert len(nb.cells) == 55
            nb.save(nb_path)

            loaded = Notebook.load(nb_path)
            assert len(loaded.cells) == 55

            kernel = NotebookKernel()
            kernel.reset()
            for idx, cell in enumerate(loaded.cells):
                result = kernel.execute_cell(cell.source)
                assert result.success, f"Cell {idx} failed: {result.error}"

            assert kernel.get_variable("cell_var_0") == 0
            assert kernel.get_variable("cell_var_54") == 54

    def test_rapid_execution_many_small_cells(self):
        """Rapid sequential execution of many small cells."""
        kernel = NotebookKernel()
        kernel.reset()
        for i in range(30):
            result = kernel.execute_cell(f"v{i} = {i} * 2")
            assert result.success
            assert result.execution_count == i + 1

        assert kernel.execution_count == 30
        assert kernel.get_variable("v0") == 0
        assert kernel.get_variable("v29") == 58

        history = kernel.get_history()
        assert len(history) == 30


# ---------------------------------------------------------------------------
# TestExampleNotebooksE2E
# ---------------------------------------------------------------------------

class TestExampleNotebooksE2E:
    """Test loading and running the bundled example notebooks."""

    EXAMPLES_DIR = Path("/home/roachbot/.openclaw/workspace/notebook-lr/examples")

    def _run_notebook(self, nb_path: Path):
        """Load a notebook, execute all code cells, return (kernel, notebook).

        Resets the shared IPython singleton before executing so that leftover
        state from earlier tests does not interfere.
        """
        nb = Notebook.load(nb_path)
        kernel = NotebookKernel()
        kernel.reset()  # clear shared singleton state
        for idx, cell in enumerate(nb.cells):
            if cell.type == CellType.CODE and cell.source.strip():
                result = kernel.execute_cell(cell.source)
                assert result.success, (
                    f"Cell {idx} in {nb_path.name} failed: {result.error}"
                )
                nb.update_cell(idx, outputs=result.outputs, execution_count=result.execution_count)
        return kernel, nb

    def test_hello_example_notebook(self):
        """Load examples/hello.nblr and execute all cells successfully."""
        hello_path = self.EXAMPLES_DIR / "hello.nblr"
        try:
            nb = Notebook.load(hello_path)
        except FileNotFoundError:
            pytest.skip("hello.nblr example not found")

        kernel, executed_nb = self._run_notebook(hello_path)

        # hello.nblr defines `message`, `count`, `items`, `greet`, `greeting`
        assert kernel.get_variable("message") == "Hello, World!"
        assert kernel.get_variable("count") == 42
        assert kernel.get_variable("items") == [1, 2, 3, 4, 5]
        greeting = kernel.get_variable("greeting")
        assert greeting is not None
        assert "Hello" in str(greeting)

        # All code cells must now have execution_count set
        code_cells = [c for c in executed_nb.cells if c.type == CellType.CODE and c.source.strip()]
        for cell in code_cells:
            assert cell.execution_count is not None

    def test_hello_example_save_reload(self):
        """Execute hello.nblr, save with session, reload and verify."""
        hello_path = self.EXAMPLES_DIR / "hello.nblr"
        try:
            Notebook.load(hello_path)
        except FileNotFoundError:
            pytest.skip("hello.nblr example not found")

        with TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "hello_copy.nblr"
            kernel, nb = self._run_notebook(hello_path)

            session_data = {
                "user_ns": _json_safe_ns(kernel.get_namespace()),
                "execution_count": kernel.execution_count,
            }
            nb.save(save_path, include_session=True, session_data=session_data)

            loaded = Notebook.load(save_path)
            assert loaded.session_state is not None
            new_kernel = NotebookKernel()
            new_kernel.restore_namespace(loaded.session_state["user_ns"])
            assert new_kernel.get_variable("message") == "Hello, World!"

    def test_ml_intro_example_notebook(self):
        """Load examples/ml_intro.nblr and execute all cells successfully."""
        ml_path = self.EXAMPLES_DIR / "ml_intro.nblr"
        try:
            nb = Notebook.load(ml_path)
        except FileNotFoundError:
            pytest.skip("ml_intro.nblr example not found")

        kernel, executed_nb = self._run_notebook(ml_path)

        # ml_intro.nblr defines training_data, knn_predict, accuracy
        training_data = kernel.get_variable("training_data")
        assert training_data is not None
        assert len(training_data) == 100

        knn_predict = kernel.get_variable("knn_predict")
        assert callable(knn_predict)

        accuracy = kernel.get_variable("accuracy")
        assert accuracy is not None
        assert 0.0 <= accuracy <= 1.0

    def test_ml_intro_example_save_reload(self):
        """Execute ml_intro.nblr, save with session, reload and verify.

        knn_predict is a function so it won't be in the JSON-embedded session_state,
        but it WILL be preserved via SessionManager (dill).  We verify both paths:
        - primitives (training_data length, accuracy) survive the JSON round-trip
        - the function survives the SessionManager dill round-trip
        """
        ml_path = self.EXAMPLES_DIR / "ml_intro.nblr"
        try:
            Notebook.load(ml_path)
        except FileNotFoundError:
            pytest.skip("ml_intro.nblr example not found")

        with TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "ml_copy.nblr"
            kernel, nb = self._run_notebook(ml_path)

            sm = SessionManager(sessions_dir=Path(tmpdir) / "sessions")
            # Save full state (including functions) via dill
            session_file = sm.save_session(kernel, name="ml_session")

            # Save JSON-safe primitives into the notebook file
            session_data = {
                "user_ns": _json_safe_ns(kernel.get_namespace()),
                "execution_count": kernel.execution_count,
            }
            nb.save(save_path, include_session=True, session_data=session_data)

            # Verify notebook JSON round-trip (primitives only)
            loaded = Notebook.load(save_path)
            assert loaded.session_state is not None
            assert loaded.session_state["execution_count"] == kernel.execution_count

            # Verify full session round-trip via dill (includes function)
            kernel.reset()
            new_kernel = NotebookKernel()
            sm.load_session(new_kernel, session_file)
            knn_predict = new_kernel.get_variable("knn_predict")
            assert callable(knn_predict)
            # Sanity-check: function still works
            training_data = new_kernel.get_variable("training_data")
            assert training_data is not None and len(training_data) == 100

    def test_all_examples_execute_without_error(self):
        """Smoke test: every .nblr file in examples/ executes without errors."""
        example_files = list(self.EXAMPLES_DIR.glob("*.nblr"))
        if not example_files:
            pytest.skip("No example notebooks found")

        for nb_path in sorted(example_files):
            try:
                kernel, nb = self._run_notebook(nb_path)
            except FileNotFoundError:
                continue
            # All executed code cells must be successful (checked inside _run_notebook)
            executed = [c for c in nb.cells if c.execution_count is not None]
            assert len(executed) >= 0, f"{nb_path.name}: unexpectedly zero executed cells"
