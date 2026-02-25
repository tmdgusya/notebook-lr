"""
Web interface for notebook-lr using Gradio.
"""

import io
import sys
from pathlib import Path
from typing import Optional

from notebook_lr import NotebookKernel, Notebook, Cell, CellType, SessionManager
from notebook_lr.utils import format_output


def launch_web(notebook: Optional[Notebook] = None, share: bool = False):
    """
    Launch the Gradio web interface.

    Args:
        notebook: Optional notebook to load
        share: Whether to create a public share link
    """
    import gradio as gr

    kernel = NotebookKernel()
    session_manager = SessionManager()

    if notebook is None:
        notebook = Notebook.new()

    # Load session if available
    if notebook.metadata.get("path"):
        checkpoint_info = session_manager.load_checkpoint(kernel, Path(notebook.metadata["path"]))
        if checkpoint_info:
            print(f"Restored session with {len(checkpoint_info['restored_vars'])} variables")

    def get_cells_info():
        """Get formatted info about all cells."""
        info = []
        for i, cell in enumerate(notebook.cells):
            cell_type = "📝" if cell.type == CellType.MARKDOWN else "🐍"
            exec_count = f"[{cell.execution_count}]" if cell.execution_count else "[ ]"
            preview = cell.source[:50].replace("\n", " ") + ("..." if len(cell.source) > 50 else "")
            info.append(f"{cell_type} {exec_count} {preview}")
        return info

    def execute_cell(cell_index: int, code: str):
        """Execute a single cell and return results."""
        if cell_index >= len(notebook.cells):
            return "Cell not found", ""

        cell = notebook.cells[cell_index]
        cell.source = code

        if cell.type == CellType.MARKDOWN:
            return "", code  # Just render markdown

        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()

        try:
            result = kernel.execute_cell(code)
            cell.outputs = result.outputs
            cell.execution_count = result.execution_count

            output_text = ""
            for output in result.outputs:
                output_text += format_output(output)

            if result.success:
                return output_text, ""
            else:
                return "", f"Error: {result.error}"
        finally:
            sys.stdout = old_stdout

    def execute_all():
        """Execute all cells in the notebook."""
        results = []
        for i, cell in enumerate(notebook.cells):
            if cell.type == CellType.CODE and cell.source.strip():
                result = kernel.execute_cell(cell.source)
                cell.outputs = result.outputs
                cell.execution_count = result.execution_count

                output_text = ""
                for output in result.outputs:
                    output_text += format_output(output)

                if result.success:
                    results.append(f"Cell {i}:\n{output_text}")
                else:
                    results.append(f"Cell {i} ERROR:\n{result.error}")
                    break

        return "\n\n---\n\n".join(results)

    def add_cell(cell_type: str, position: str):
        """Add a new cell."""
        cell = Cell(type=CellType.CODE if cell_type == "code" else CellType.MARKDOWN, source="")
        if position == "end":
            notebook.add_cell(cell)
        else:
            notebook.insert_cell(0, cell)
        return get_cells_info()

    def update_cell(cell_index: int, code: str):
        """Update a cell's source."""
        if 0 <= cell_index < len(notebook.cells):
            notebook.cells[cell_index].source = code
        return get_cells_info()

    def delete_cell(cell_index: int):
        """Delete a cell."""
        if 0 <= cell_index < len(notebook.cells):
            notebook.remove_cell(cell_index)
        return get_cells_info()

    def save_notebook(include_session: bool):
        """Save notebook to file."""
        path = notebook.metadata.get("path", "notebook.nblr")
        if include_session:
            session_data = {
                "user_ns": kernel.get_namespace(),
                "execution_count": kernel.execution_count,
            }
            notebook.save(Path(path), include_session=True, session_data=session_data)
            session_manager.save_checkpoint(kernel, Path(path))
        else:
            notebook.save(Path(path))
        return f"Saved to {path}"

    def load_notebook(file_path):
        """Load notebook from file."""
        nonlocal notebook
        if file_path:
            notebook = Notebook.load(Path(file_path.name))
            notebook.metadata["path"] = file_path.name
            return get_cells_info(), f"Loaded {file_path.name}"
        return get_cells_info(), "No file selected"

    def get_variables():
        """Get all variables in namespace."""
        variables = kernel.get_defined_names()
        result = []
        for name in sorted(variables):
            value = kernel.get_variable(name)
            var_type = type(value).__name__
            result.append(f"{name}: {var_type} = {repr(value)[:100]}")
        return "\n".join(result) if result else "No variables defined"

    # Build Gradio interface
    with gr.Blocks(title="notebook-lr", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# 📓 notebook-lr")
        gr.Markdown("A Jupyter-like notebook with persistent session context")

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### Cells")
                cell_list = gr.Dropdown(choices=get_cells_info(), label="Notebook Cells", interactive=True)

                with gr.Row():
                    add_code_btn = gr.Button("Add Code Cell")
                    add_md_btn = gr.Button("Add Markdown Cell")

                delete_btn = gr.Button("Delete Cell", variant="secondary")

            with gr.Column(scale=3):
                gr.Markdown("### Cell Editor")
                cell_type_display = gr.Textbox(label="Cell Type", interactive=False)
                code_input = gr.Code(language="python", label="Cell Source", lines=10)

                with gr.Row():
                    execute_btn = gr.Button("▶ Execute Cell", variant="primary")
                    execute_all_btn = gr.Button("▶▶ Execute All")

                output_display = gr.TextArea(label="Output", lines=5)
                error_display = gr.TextArea(label="Errors", lines=3, interactive=False)

        with gr.Accordion("File Operations", open=False):
            with gr.Row():
                save_btn = gr.Button("💾 Save")
                save_session_btn = gr.Button("💾 Save with Session")

            load_file = gr.File(label="Load Notebook", file_types=[".nblr"])
            save_status = gr.Textbox(label="Status")

        with gr.Accordion("Session Info", open=False):
            vars_btn = gr.Button("Show Variables")
            vars_display = gr.TextArea(label="Variables in Namespace", lines=10)
            clear_btn = gr.Button("Clear Variables")

        # Event handlers
        def select_cell(evt: gr.SelectData):
            if evt.index < len(notebook.cells):
                cell = notebook.cells[evt.index]
                return (
                    cell.type.value,
                    cell.source,
                    "",
                    ""
                )
            return "", "", "", ""

        cell_list.select(select_cell, outputs=[cell_type_display, code_input, output_display, error_display])

        execute_btn.click(
            execute_cell,
            inputs=[cell_list, code_input],
            outputs=[output_display, error_display]
        )

        execute_all_btn.click(
            execute_all,
            outputs=output_display
        )

        add_code_btn.click(
            lambda: add_cell("code", "end"),
            outputs=cell_list
        )

        add_md_btn.click(
            lambda: add_cell("markdown", "end"),
            outputs=cell_list
        )

        delete_btn.click(
            delete_cell,
            inputs=[cell_list],
            outputs=cell_list
        )

        save_btn.click(
            lambda: save_notebook(False),
            outputs=save_status
        )

        save_session_btn.click(
            lambda: save_notebook(True),
            outputs=save_status
        )

        load_file.change(
            load_notebook,
            inputs=load_file,
            outputs=[cell_list, save_status]
        )

        vars_btn.click(
            get_variables,
            outputs=vars_display
        )

        clear_btn.click(
            lambda: (kernel.reset(), "Variables cleared"),
            outputs=vars_display
        )

    demo.launch(share=share)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        nb = Notebook.load(Path(sys.argv[1]))
        launch_web(nb)
    else:
        launch_web()
