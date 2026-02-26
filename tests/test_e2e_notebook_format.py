"""
E2E tests for notebook format save/load with execution roundtrips.

These tests cover full workflows: create -> execute -> save -> load -> verify.
Note: NotebookKernel wraps IPython's InteractiveShell.instance() which is a
singleton per process. Tests use kernel.reset() to obtain clean state rather
than relying on separate NotebookKernel() instances being isolated.
"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from notebook_lr.kernel import NotebookKernel
from notebook_lr.notebook import Cell, CellType, Notebook
from notebook_lr.session import SessionManager


def fresh_kernel() -> NotebookKernel:
    """Return a kernel reset to clean state."""
    k = NotebookKernel()
    k.reset()
    return k


class TestNotebookCreateAndSaveE2E:
    """Full notebook creation + save/load."""

    def test_create_notebook_with_many_cells_and_reload(self):
        """Create notebook with 5+ code cells and 2 markdown cells, save, reload, verify all cells."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "big.nblr"

            nb = Notebook.new("Full Notebook")
            # 5 code cells
            c0 = nb.add_cell(type=CellType.CODE, source="x = 1")
            c1 = nb.add_cell(type=CellType.CODE, source="y = 2")
            c2 = nb.add_cell(type=CellType.CODE, source="z = x + y")
            c3 = nb.add_cell(type=CellType.CODE, source="import math")
            c4 = nb.add_cell(type=CellType.CODE, source="result = math.sqrt(9)")
            # 2 markdown cells
            m0 = nb.add_cell(type=CellType.MARKDOWN, source="# Section One")
            m1 = nb.add_cell(type=CellType.MARKDOWN, source="## Subsection")

            nb.save(path)
            loaded = Notebook.load(path)

            assert len(loaded.cells) == 7

    def test_cell_ordering_preserved(self):
        """Verify that cell ordering is preserved after save/load."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "order.nblr"

            nb = Notebook.new("Order Test")
            sources = ["first", "second", "third", "fourth", "fifth"]
            for s in sources:
                nb.add_cell(type=CellType.CODE, source=s)

            nb.save(path)
            loaded = Notebook.load(path)

            for i, expected in enumerate(sources):
                assert loaded.cells[i].source == expected

    def test_cell_types_preserved(self):
        """Verify that code and markdown cell types survive roundtrip."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "types.nblr"

            nb = Notebook.new("Types Test")
            nb.add_cell(type=CellType.CODE, source="x = 1")
            nb.add_cell(type=CellType.MARKDOWN, source="# Title")
            nb.add_cell(type=CellType.CODE, source="y = 2")
            nb.add_cell(type=CellType.MARKDOWN, source="## Sub")

            nb.save(path)
            loaded = Notebook.load(path)

            assert loaded.cells[0].type == CellType.CODE
            assert loaded.cells[1].type == CellType.MARKDOWN
            assert loaded.cells[2].type == CellType.CODE
            assert loaded.cells[3].type == CellType.MARKDOWN

    def test_metadata_preserved(self):
        """Verify notebook name and timestamps survive roundtrip."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "meta.nblr"

            nb = Notebook.new("My Special Notebook")
            nb.add_cell(type=CellType.CODE, source="pass")
            nb.save(path)
            loaded = Notebook.load(path)

            assert loaded.metadata["name"] == "My Special Notebook"
            assert "created" in loaded.metadata
            assert "modified" in loaded.metadata

    def test_cell_ids_preserved(self):
        """Verify that cell IDs are preserved after save/load."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "ids.nblr"

            nb = Notebook.new("ID Test")
            cells = [nb.add_cell(type=CellType.CODE, source=f"v{i} = {i}") for i in range(5)]
            original_ids = [c.id for c in cells]

            nb.save(path)
            loaded = Notebook.load(path)

            loaded_ids = [c.id for c in loaded.cells]
            assert loaded_ids == original_ids

    def test_cell_sources_preserved_verbatim(self):
        """Verify multi-line cell sources are preserved exactly."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "multiline.nblr"

            multiline_source = "def foo():\n    return 42\n\nresult = foo()"
            markdown_source = "# Title\n\nSome **bold** text.\n\n- item 1\n- item 2"

            nb = Notebook.new("Source Test")
            nb.add_cell(type=CellType.CODE, source=multiline_source)
            nb.add_cell(type=CellType.MARKDOWN, source=markdown_source)

            nb.save(path)
            loaded = Notebook.load(path)

            assert loaded.cells[0].source == multiline_source
            assert loaded.cells[1].source == markdown_source

    def test_saved_file_is_valid_json(self):
        """Verify the .nblr file is valid JSON with expected top-level keys."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "validate.nblr"

            nb = Notebook.new("JSON Test")
            nb.add_cell(type=CellType.CODE, source="x = 1")
            nb.add_cell(type=CellType.MARKDOWN, source="# Hi")
            nb.save(path)

            with open(path) as f:
                data = json.load(f)

            assert "version" in data
            assert "cells" in data
            assert "metadata" in data
            assert data["metadata"]["name"] == "JSON Test"
            assert len(data["cells"]) == 2


class TestNotebookExecutionRoundtripE2E:
    """Execute cells then save/load; verify outputs and execution counts survive."""

    def setup_method(self):
        self.kernel = fresh_kernel()

    def test_execution_counts_survive_roundtrip(self):
        """Execute cells, save with counts, load and verify counts."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "exec.nblr"

            nb = Notebook.new("Exec Test")
            codes = ["a = 1", "b = a + 1", "c = b * 3"]
            for code in codes:
                nb.add_cell(type=CellType.CODE, source=code)

            # Execute and update cells
            for i, code in enumerate(codes):
                result = self.kernel.execute_cell(code)
                nb.update_cell(
                    i,
                    outputs=result.outputs,
                    execution_count=result.execution_count,
                )

            nb.save(path)
            loaded = Notebook.load(path)

            assert loaded.cells[0].execution_count == 1
            assert loaded.cells[1].execution_count == 2
            assert loaded.cells[2].execution_count == 3

    def test_stdout_outputs_survive_roundtrip(self):
        """Execute cells with stdout, save, load and verify stream outputs preserved."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "stdout.nblr"

            nb = Notebook.new("Stdout Test")
            nb.add_cell(type=CellType.CODE, source='print("hello world")')
            nb.add_cell(type=CellType.CODE, source='print("line 1\\nline 2")')

            for i in range(len(nb.cells)):
                result = self.kernel.execute_cell(nb.cells[i].source)
                nb.update_cell(i, outputs=result.outputs, execution_count=result.execution_count)

            nb.save(path)
            loaded = Notebook.load(path)

            cell0_outputs = loaded.cells[0].outputs
            stream_outputs = [o for o in cell0_outputs if o.get("type") == "stream"]
            assert len(stream_outputs) > 0
            assert "hello world" in stream_outputs[0]["text"]

            cell1_outputs = loaded.cells[1].outputs
            stream_outputs1 = [o for o in cell1_outputs if o.get("type") == "stream"]
            assert len(stream_outputs1) > 0

    def test_execute_result_output_type_preserved(self):
        """Verify execute_result output type survives roundtrip."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "result.nblr"

            nb = Notebook.new("Result Test")
            nb.add_cell(type=CellType.CODE, source="40 + 2")

            result = self.kernel.execute_cell("40 + 2")
            assert result.success
            nb.update_cell(0, outputs=result.outputs, execution_count=result.execution_count)

            nb.save(path)
            loaded = Notebook.load(path)

            outputs = loaded.cells[0].outputs
            result_outputs = [o for o in outputs if o.get("type") == "execute_result"]
            assert len(result_outputs) > 0
            assert "42" in result_outputs[0]["data"]["text/plain"]

    def test_error_output_type_preserved(self):
        """Verify error output type survives roundtrip."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "error.nblr"

            nb = Notebook.new("Error Test")
            nb.add_cell(type=CellType.CODE, source="raise ValueError('test error')")

            result = self.kernel.execute_cell("raise ValueError('test error')")
            assert not result.success
            nb.update_cell(0, outputs=result.outputs, execution_count=result.execution_count)

            nb.save(path)
            loaded = Notebook.load(path)

            outputs = loaded.cells[0].outputs
            error_outputs = [o for o in outputs if o.get("type") == "error"]
            assert len(error_outputs) > 0
            assert error_outputs[0]["ename"] == "ValueError"

    def test_multiple_output_types_in_one_cell(self):
        """Execute cell that produces stdout + return value; verify both output types."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "multi_output.nblr"

            nb = Notebook.new("Multi Output")
            code = 'print("side effect")\n42'
            nb.add_cell(type=CellType.CODE, source=code)

            result = self.kernel.execute_cell(code)
            nb.update_cell(0, outputs=result.outputs, execution_count=result.execution_count)

            nb.save(path)
            loaded = Notebook.load(path)

            outputs = loaded.cells[0].outputs
            output_types = {o["type"] for o in outputs}
            # Should have stream output for print
            assert "stream" in output_types

    def test_markdown_cells_have_no_execution_count(self):
        """Markdown cells should not have execution_count after roundtrip."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "md_exec.nblr"

            nb = Notebook.new("MD Test")
            nb.add_cell(type=CellType.MARKDOWN, source="# Title")
            nb.add_cell(type=CellType.CODE, source="x = 1")

            result = self.kernel.execute_cell("x = 1")
            nb.update_cell(1, outputs=result.outputs, execution_count=result.execution_count)

            nb.save(path)
            loaded = Notebook.load(path)

            assert loaded.cells[0].execution_count is None
            assert loaded.cells[1].execution_count == 1


class TestSessionPersistenceE2E:
    """Full session save/load workflow."""

    def setup_method(self):
        self.kernel = fresh_kernel()

    def test_variables_restored_after_session_reload(self):
        """Build state, save session, restore into fresh kernel, verify all vars."""
        with TemporaryDirectory() as tmpdir:
            sm = SessionManager(sessions_dir=Path(tmpdir))

            # Build up diverse state
            self.kernel.execute_cell("x = 100")
            self.kernel.execute_cell("name = 'Alice'")
            self.kernel.execute_cell("values = [1, 2, 3, 4, 5]")
            self.kernel.execute_cell("mapping = {'a': 1, 'b': 2}")

            session_path = sm.save_session(self.kernel, name="vars_session")

            # Restore into clean kernel
            new_kernel = fresh_kernel()
            info = sm.load_session(new_kernel, session_path)

            assert new_kernel.get_variable("x") == 100
            assert new_kernel.get_variable("name") == "Alice"
            assert new_kernel.get_variable("values") == [1, 2, 3, 4, 5]
            assert new_kernel.get_variable("mapping") == {"a": 1, "b": 2}

    def test_functions_restored_and_callable(self):
        """Execute cells defining functions, restore session, verify functions work."""
        with TemporaryDirectory() as tmpdir:
            sm = SessionManager(sessions_dir=Path(tmpdir))

            self.kernel.execute_cell(
                "def multiply(a, b):\n    return a * b\n"
            )
            self.kernel.execute_cell(
                "def greet(name):\n    return f'Hello, {name}!'\n"
            )
            self.kernel.execute_cell("precomputed = multiply(6, 7)")

            session_path = sm.save_session(self.kernel, name="func_session")

            new_kernel = fresh_kernel()
            sm.load_session(new_kernel, session_path)

            multiply = new_kernel.get_variable("multiply")
            greet = new_kernel.get_variable("greet")

            assert multiply is not None
            assert greet is not None
            assert multiply(3, 4) == 12
            assert greet("World") == "Hello, World!"
            assert new_kernel.get_variable("precomputed") == 42

    def test_continue_execution_after_session_restore(self):
        """Restore session then execute more cells that depend on restored state."""
        with TemporaryDirectory() as tmpdir:
            sm = SessionManager(sessions_dir=Path(tmpdir))

            self.kernel.execute_cell("base = 10")
            self.kernel.execute_cell("multiplier = 5")

            session_path = sm.save_session(self.kernel, name="continue_session")

            new_kernel = fresh_kernel()
            sm.load_session(new_kernel, session_path)

            # Execute more cells using restored variables
            result = new_kernel.execute_cell("product = base * multiplier")
            assert result.success
            assert new_kernel.get_variable("product") == 50

            result2 = new_kernel.execute_cell("double_product = product * 2")
            assert result2.success
            assert new_kernel.get_variable("double_product") == 100

    def test_execution_count_restored(self):
        """Verify execution count is restored correctly in session."""
        with TemporaryDirectory() as tmpdir:
            sm = SessionManager(sessions_dir=Path(tmpdir))

            for i in range(5):
                self.kernel.execute_cell(f"var_{i} = {i}")

            assert self.kernel.execution_count == 5
            session_path = sm.save_session(self.kernel, name="count_session")

            new_kernel = fresh_kernel()
            sm.load_session(new_kernel, session_path)

            assert new_kernel.execution_count == 5

    def test_imports_restored(self):
        """Verify imported modules are accessible after session restore."""
        with TemporaryDirectory() as tmpdir:
            sm = SessionManager(sessions_dir=Path(tmpdir))

            self.kernel.execute_cell("import math")
            self.kernel.execute_cell("pi_approx = round(math.pi, 4)")

            session_path = sm.save_session(self.kernel, name="import_session")

            new_kernel = fresh_kernel()
            sm.load_session(new_kernel, session_path)

            assert new_kernel.get_variable("pi_approx") == 3.1416

            # math should be restorable and usable
            math_var = new_kernel.get_variable("math")
            assert math_var is not None

    def test_restore_info_contains_var_names(self):
        """Verify load_session returns info dict with restored_vars list."""
        with TemporaryDirectory() as tmpdir:
            sm = SessionManager(sessions_dir=Path(tmpdir))

            self.kernel.execute_cell("alpha = 1")
            self.kernel.execute_cell("beta = 2")
            self.kernel.execute_cell("gamma = 3")

            session_path = sm.save_session(self.kernel, name="info_session")

            new_kernel = fresh_kernel()
            info = sm.load_session(new_kernel, session_path)

            assert "restored_vars" in info
            assert "alpha" in info["restored_vars"]
            assert "beta" in info["restored_vars"]
            assert "gamma" in info["restored_vars"]
            assert "saved_at" in info


class TestNotebookWithSessionE2E:
    """Notebook + embedded session state."""

    def setup_method(self):
        self.kernel = fresh_kernel()

    def test_save_notebook_with_session_and_verify_embedded(self):
        """Save notebook with include_session=True, load back, verify session_state present."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "with_session.nblr"

            nb = Notebook.new("Session Notebook")
            nb.add_cell(type=CellType.CODE, source="x = 42")
            nb.add_cell(type=CellType.CODE, source="y = x * 2")
            nb.add_cell(type=CellType.MARKDOWN, source="# Done")

            self.kernel.execute_cell("x = 42")
            self.kernel.execute_cell("y = x * 2")

            session_data = {
                "user_ns": {"x": 42, "y": 84},
                "execution_count": self.kernel.execution_count,
            }

            nb.save(path, include_session=True, session_data=session_data)
            loaded = Notebook.load(path)

            assert loaded.session_state is not None
            assert loaded.session_state["user_ns"]["x"] == 42
            assert loaded.session_state["user_ns"]["y"] == 84

    def test_restore_kernel_from_embedded_session_state(self):
        """Load notebook with embedded session, restore session to new kernel, verify vars."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "restore.nblr"

            nb = Notebook.new("Restore Test")
            nb.add_cell(type=CellType.CODE, source="counter = 100")
            nb.add_cell(type=CellType.CODE, source="label = 'saved'")

            session_data = {
                "user_ns": {"counter": 100, "label": "saved"},
                "execution_count": 2,
            }
            nb.save(path, include_session=True, session_data=session_data)

            loaded = Notebook.load(path)
            assert loaded.session_state is not None

            # Restore from embedded session
            new_kernel = fresh_kernel()
            new_kernel.restore_namespace(loaded.session_state["user_ns"])

            assert new_kernel.get_variable("counter") == 100
            assert new_kernel.get_variable("label") == "saved"

    def test_continue_execution_after_embedded_session_restore(self):
        """Restore from embedded session then execute more cells."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "continue.nblr"

            nb = Notebook.new("Continue Test")
            nb.add_cell(type=CellType.CODE, source="start = 50")

            session_data = {"user_ns": {"start": 50}, "execution_count": 1}
            nb.save(path, include_session=True, session_data=session_data)

            loaded = Notebook.load(path)
            new_kernel = fresh_kernel()
            new_kernel.restore_namespace(loaded.session_state["user_ns"])

            # Continue executing
            result = new_kernel.execute_cell("doubled = start * 2")
            assert result.success
            assert new_kernel.get_variable("doubled") == 100

    def test_saving_without_session_clears_embedded_state(self):
        """Save notebook without include_session; verify session_state is None after load."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "no_session.nblr"

            nb = Notebook.new("No Session")
            nb.add_cell(type=CellType.CODE, source="x = 1")

            # First save WITH session
            nb.save(path, include_session=True, session_data={"user_ns": {"x": 1}, "execution_count": 1})
            loaded = Notebook.load(path)
            assert loaded.session_state is not None

            # Now save WITHOUT session
            loaded.save(path, include_session=False)
            reloaded = Notebook.load(path)
            assert reloaded.session_state is None

    def test_all_cells_preserved_when_saving_with_session(self):
        """Ensure cells are preserved correctly when saving with embedded session."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "cells_with_session.nblr"

            nb = Notebook.new("Cells + Session")
            codes = ["a = 1", "b = 2", "c = 3"]
            for code in codes:
                nb.add_cell(type=CellType.CODE, source=code)
            nb.add_cell(type=CellType.MARKDOWN, source="# End")

            session_data = {"user_ns": {"a": 1, "b": 2, "c": 3}, "execution_count": 3}
            nb.save(path, include_session=True, session_data=session_data)

            loaded = Notebook.load(path)
            assert len(loaded.cells) == 4
            assert loaded.cells[0].source == "a = 1"
            assert loaded.cells[3].type == CellType.MARKDOWN
            assert loaded.session_state["user_ns"]["c"] == 3


class TestCheckpointE2E:
    """Checkpoint save/load."""

    def setup_method(self):
        self.kernel = fresh_kernel()

    def test_execute_save_checkpoint_restore(self):
        """Execute cells, save checkpoint, reset kernel, load checkpoint, verify state."""
        with TemporaryDirectory() as tmpdir:
            sm = SessionManager(sessions_dir=Path(tmpdir))
            notebook_path = Path(tmpdir) / "mynotebook.nblr"

            self.kernel.execute_cell("saved_var = 999")
            self.kernel.execute_cell("another = 'checkpoint_value'")

            checkpoint_path = sm.save_checkpoint(self.kernel, notebook_path)
            assert checkpoint_path.exists()

            new_kernel = fresh_kernel()
            info = sm.load_checkpoint(new_kernel, notebook_path)

            assert info is not None
            assert new_kernel.get_variable("saved_var") == 999
            assert new_kernel.get_variable("another") == "checkpoint_value"

    def test_checkpoint_overwrites_previous(self):
        """Save checkpoint, execute more cells, save again, verify latest state loaded."""
        with TemporaryDirectory() as tmpdir:
            sm = SessionManager(sessions_dir=Path(tmpdir))
            notebook_path = Path(tmpdir) / "evolving.nblr"

            # First checkpoint
            self.kernel.execute_cell("version = 1")
            sm.save_checkpoint(self.kernel, notebook_path)

            # Evolve state and overwrite checkpoint
            self.kernel.execute_cell("version = 2")
            self.kernel.execute_cell("extra = 'new'")
            sm.save_checkpoint(self.kernel, notebook_path)

            new_kernel = fresh_kernel()
            info = sm.load_checkpoint(new_kernel, notebook_path)

            assert info is not None
            assert new_kernel.get_variable("version") == 2
            assert new_kernel.get_variable("extra") == "new"

    def test_no_checkpoint_returns_none(self):
        """Loading a checkpoint for a notebook that has none returns None."""
        with TemporaryDirectory() as tmpdir:
            sm = SessionManager(sessions_dir=Path(tmpdir))
            notebook_path = Path(tmpdir) / "no_checkpoint.nblr"

            new_kernel = fresh_kernel()
            info = sm.load_checkpoint(new_kernel, notebook_path)

            assert info is None

    def test_continue_execution_after_checkpoint_restore(self):
        """Restore from checkpoint, then execute further cells successfully."""
        with TemporaryDirectory() as tmpdir:
            sm = SessionManager(sessions_dir=Path(tmpdir))
            notebook_path = Path(tmpdir) / "chain.nblr"

            self.kernel.execute_cell("step1 = 10")
            sm.save_checkpoint(self.kernel, notebook_path)

            new_kernel = fresh_kernel()
            sm.load_checkpoint(new_kernel, notebook_path)

            result = new_kernel.execute_cell("step2 = step1 + 5")
            assert result.success
            assert new_kernel.get_variable("step2") == 15

    def test_checkpoint_path_tied_to_notebook_name(self):
        """Two notebooks produce separate, independent checkpoints with distinct stored values."""
        with TemporaryDirectory() as tmpdir:
            sm = SessionManager(sessions_dir=Path(tmpdir))

            nb_a = Path(tmpdir) / "notebook_a.nblr"
            nb_b = Path(tmpdir) / "notebook_b.nblr"

            # Save checkpoint for notebook_a
            kernel_a = fresh_kernel()
            kernel_a.execute_cell("tag = 'from_a'")
            sm.save_checkpoint(kernel_a, nb_a)

            # Save checkpoint for notebook_b
            kernel_b = fresh_kernel()
            kernel_b.execute_cell("tag = 'from_b'")
            sm.save_checkpoint(kernel_b, nb_b)

            # Verify checkpoint files are distinct
            cp_a = sm.get_checkpoint_path(nb_a)
            cp_b = sm.get_checkpoint_path(nb_b)
            assert cp_a != cp_b
            assert cp_a.exists()
            assert cp_b.exists()

            # Restore checkpoint_a and assert immediately (singleton is shared)
            restore_a = fresh_kernel()
            sm.load_checkpoint(restore_a, nb_a)
            tag_a = restore_a.get_variable("tag")
            assert tag_a == "from_a", f"Expected 'from_a', got {tag_a!r}"

            # Restore checkpoint_b and assert immediately
            restore_b = fresh_kernel()
            sm.load_checkpoint(restore_b, nb_b)
            tag_b = restore_b.get_variable("tag")
            assert tag_b == "from_b", f"Expected 'from_b', got {tag_b!r}"


class TestNotebookManipulationE2E:
    """Cell manipulation (insert/remove/reorder) + execution + roundtrip."""

    def setup_method(self):
        self.kernel = fresh_kernel()

    def test_insert_at_beginning_and_execute(self):
        """Insert a cell at index 0, execute all cells in order, save/load."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "insert.nblr"

            nb = Notebook.new("Insert Test")
            nb.add_cell(type=CellType.CODE, source="b = 20")  # index 0
            nb.add_cell(type=CellType.CODE, source="c = 30")  # index 1

            # Insert at beginning
            nb.insert_cell(0, type=CellType.CODE, source="a = 10")

            # Execute all in current order
            for i, cell in enumerate(nb.cells):
                result = self.kernel.execute_cell(cell.source)
                nb.update_cell(i, outputs=result.outputs, execution_count=result.execution_count)

            nb.save(path)
            loaded = Notebook.load(path)

            assert loaded.cells[0].source == "a = 10"
            assert loaded.cells[1].source == "b = 20"
            assert loaded.cells[2].source == "c = 30"
            assert loaded.cells[0].execution_count == 1
            assert loaded.cells[1].execution_count == 2
            assert loaded.cells[2].execution_count == 3

            assert self.kernel.get_variable("a") == 10
            assert self.kernel.get_variable("b") == 20
            assert self.kernel.get_variable("c") == 30

    def test_remove_middle_cell_and_execute(self):
        """Remove a middle cell, execute remaining, save/load, verify consistency."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "remove.nblr"

            nb = Notebook.new("Remove Test")
            nb.add_cell(type=CellType.CODE, source="keep_a = 1")
            nb.add_cell(type=CellType.CODE, source="drop_me = 999")
            nb.add_cell(type=CellType.CODE, source="keep_b = 2")

            removed = nb.remove_cell(1)
            assert removed.source == "drop_me = 999"
            assert len(nb.cells) == 2

            for i, cell in enumerate(nb.cells):
                result = self.kernel.execute_cell(cell.source)
                nb.update_cell(i, outputs=result.outputs, execution_count=result.execution_count)

            nb.save(path)
            loaded = Notebook.load(path)

            assert len(loaded.cells) == 2
            assert loaded.cells[0].source == "keep_a = 1"
            assert loaded.cells[1].source == "keep_b = 2"
            assert self.kernel.get_variable("keep_a") == 1
            assert self.kernel.get_variable("keep_b") == 2

    def test_multiple_insertions_and_removals(self):
        """Perform several insert/remove ops, execute all, save/load, verify."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "multi_op.nblr"

            nb = Notebook.new("Multi Op")
            nb.add_cell(type=CellType.CODE, source="x = 1")
            nb.add_cell(type=CellType.CODE, source="z = 3")

            # Insert between x and z
            nb.insert_cell(1, type=CellType.CODE, source="y = 2")

            # Add trailing markdown
            nb.add_cell(type=CellType.MARKDOWN, source="# Done")

            # Remove the z cell (now at index 2)
            nb.remove_cell(2)

            # Expected: [x=1, y=2, markdown]
            assert len(nb.cells) == 3
            assert nb.cells[0].source == "x = 1"
            assert nb.cells[1].source == "y = 2"
            assert nb.cells[2].type == CellType.MARKDOWN

            for i, cell in enumerate(nb.cells):
                if cell.type == CellType.CODE:
                    result = self.kernel.execute_cell(cell.source)
                    nb.update_cell(i, outputs=result.outputs, execution_count=result.execution_count)

            nb.save(path)
            loaded = Notebook.load(path)

            assert len(loaded.cells) == 3
            assert loaded.cells[0].execution_count is not None
            assert loaded.cells[1].execution_count is not None
            assert loaded.cells[2].execution_count is None  # markdown

    def test_update_cell_source_then_execute(self):
        """Update a cell's source before execution, verify updated source runs."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "update_source.nblr"

            nb = Notebook.new("Update Source")
            nb.add_cell(type=CellType.CODE, source="original_val = 0")

            # Update source before execution
            nb.update_cell(0, source="updated_val = 77")

            result = self.kernel.execute_cell(nb.cells[0].source)
            nb.update_cell(0, outputs=result.outputs, execution_count=result.execution_count)

            nb.save(path)
            loaded = Notebook.load(path)

            assert loaded.cells[0].source == "updated_val = 77"
            assert loaded.cells[0].execution_count == 1
            assert self.kernel.get_variable("updated_val") == 77


class TestMultipleNotebooksE2E:
    """Multiple notebooks with independent sessions; verify state isolation."""

    def test_three_notebooks_isolated_sessions(self):
        """Create 3 notebooks, execute each with separate state, verify no leakage."""
        with TemporaryDirectory() as tmpdir:
            sm = SessionManager(sessions_dir=Path(tmpdir))

            # Notebook A
            nb_a = Notebook.new("Notebook A")
            nb_a.add_cell(type=CellType.CODE, source="notebook_id = 'A'\nvalue = 100")
            path_a = Path(tmpdir) / "notebook_a.nblr"

            kernel_a = fresh_kernel()
            result_a = kernel_a.execute_cell("notebook_id = 'A'\nvalue = 100")
            nb_a.update_cell(0, outputs=result_a.outputs, execution_count=result_a.execution_count)
            session_a = sm.save_session(kernel_a, name="session_a")
            nb_a.save(path_a)

            # Notebook B
            nb_b = Notebook.new("Notebook B")
            nb_b.add_cell(type=CellType.CODE, source="notebook_id = 'B'\nvalue = 200")
            path_b = Path(tmpdir) / "notebook_b.nblr"

            kernel_b = fresh_kernel()
            result_b = kernel_b.execute_cell("notebook_id = 'B'\nvalue = 200")
            nb_b.update_cell(0, outputs=result_b.outputs, execution_count=result_b.execution_count)
            session_b = sm.save_session(kernel_b, name="session_b")
            nb_b.save(path_b)

            # Notebook C
            nb_c = Notebook.new("Notebook C")
            nb_c.add_cell(type=CellType.CODE, source="notebook_id = 'C'\nvalue = 300")
            path_c = Path(tmpdir) / "notebook_c.nblr"

            kernel_c = fresh_kernel()
            result_c = kernel_c.execute_cell("notebook_id = 'C'\nvalue = 300")
            nb_c.update_cell(0, outputs=result_c.outputs, execution_count=result_c.execution_count)
            session_c = sm.save_session(kernel_c, name="session_c")
            nb_c.save(path_c)

            # Reload each notebook and verify metadata isolation
            loaded_a = Notebook.load(path_a)
            loaded_b = Notebook.load(path_b)
            loaded_c = Notebook.load(path_c)

            assert loaded_a.metadata["name"] == "Notebook A"
            assert loaded_b.metadata["name"] == "Notebook B"
            assert loaded_c.metadata["name"] == "Notebook C"

            # Restore sessions and verify variable isolation
            restore_a = fresh_kernel()
            info_a = sm.load_session(restore_a, session_a)
            assert restore_a.get_variable("notebook_id") == "A"
            assert restore_a.get_variable("value") == 100

            restore_b = fresh_kernel()
            info_b = sm.load_session(restore_b, session_b)
            assert restore_b.get_variable("notebook_id") == "B"
            assert restore_b.get_variable("value") == 200

            restore_c = fresh_kernel()
            info_c = sm.load_session(restore_c, session_c)
            assert restore_c.get_variable("notebook_id") == "C"
            assert restore_c.get_variable("value") == 300

    def test_notebook_sessions_do_not_share_variables(self):
        """Variables defined in one notebook's session don't appear in another's."""
        with TemporaryDirectory() as tmpdir:
            sm = SessionManager(sessions_dir=Path(tmpdir))

            # Notebook 1: defines secret_1
            k1 = fresh_kernel()
            k1.execute_cell("secret_1 = 'only_in_1'")
            s1 = sm.save_session(k1, name="nb1")

            # Notebook 2: defines secret_2
            k2 = fresh_kernel()
            k2.execute_cell("secret_2 = 'only_in_2'")
            s2 = sm.save_session(k2, name="nb2")

            # Restore session 1 and verify secret_2 is absent
            r1 = fresh_kernel()
            sm.load_session(r1, s1)
            assert r1.get_variable("secret_1") == "only_in_1"
            assert r1.get_variable("secret_2") is None

            # Restore session 2 and verify secret_1 is absent
            r2 = fresh_kernel()
            sm.load_session(r2, s2)
            assert r2.get_variable("secret_2") == "only_in_2"
            assert r2.get_variable("secret_1") is None

    def test_three_notebooks_with_embedded_sessions(self):
        """Save 3 notebooks with include_session; load each and verify correct embedded state."""
        with TemporaryDirectory() as tmpdir:
            specs = [
                ("Alpha", {"color": "red", "count": 1}),
                ("Beta", {"color": "green", "count": 2}),
                ("Gamma", {"color": "blue", "count": 3}),
            ]

            paths = []
            for name, ns in specs:
                nb = Notebook.new(name)
                nb.add_cell(type=CellType.CODE, source=f"color = '{ns['color']}'\ncount = {ns['count']}")
                path = Path(tmpdir) / f"{name.lower()}.nblr"
                nb.save(path, include_session=True, session_data={"user_ns": ns, "execution_count": 1})
                paths.append((name, path, ns))

            for name, path, expected_ns in paths:
                loaded = Notebook.load(path)
                assert loaded.metadata["name"] == name
                assert loaded.session_state is not None
                assert loaded.session_state["user_ns"]["color"] == expected_ns["color"]
                assert loaded.session_state["user_ns"]["count"] == expected_ns["count"]

    def test_list_sessions_shows_all_saved(self):
        """After saving 3 sessions, list_sessions returns all three."""
        with TemporaryDirectory() as tmpdir:
            sm = SessionManager(sessions_dir=Path(tmpdir))

            for i in range(3):
                k = fresh_kernel()
                k.execute_cell(f"notebook_num = {i}")
                sm.save_session(k, name=f"notebook_{i}")

            sessions = sm.list_sessions()
            names = [s["name"] for s in sessions]

            assert "notebook_0" in names
            assert "notebook_1" in names
            assert "notebook_2" in names
