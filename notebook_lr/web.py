"""
Web interface for notebook-lr using Gradio.
"""

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
        checkpoint_info = session_manager.load_checkpoint(
            kernel, Path(notebook.metadata["path"])
        )
        if checkpoint_info:
            print(
                f"Restored session with {len(checkpoint_info['restored_vars'])} variables"
            )

    def get_cell_choices():
        """Get formatted info about all cells."""
        choices = []
        for i, cell in enumerate(notebook.cells):
            type_label = "Code" if cell.type == CellType.CODE else "Markdown"
            exec_count = (
                f"[{cell.execution_count}]" if cell.execution_count else "[ ]"
            )
            status = ""
            if cell.outputs and any(o.get("type") == "error" for o in cell.outputs):
                status = " ERR"
            elif cell.execution_count is not None:
                status = " OK"
            preview = cell.source[:40].replace("\n", " ")
            if len(cell.source) > 40:
                preview += "..."
            choices.append(f"{i}: {type_label} {exec_count}{status} | {preview}")
        return choices

    def get_notebook_info():
        """Get notebook info string."""
        name = notebook.metadata.get("name", "Untitled")
        cell_count = len(notebook.cells)
        code_count = sum(1 for c in notebook.cells if c.type == CellType.CODE)
        md_count = cell_count - code_count
        executed = sum(1 for c in notebook.cells if c.execution_count is not None)
        return (
            f"**{name}** | {cell_count} cells "
            f"({code_count} code, {md_count} markdown) | "
            f"{executed} executed"
        )

    def select_cell(evt: gr.SelectData):
        """Handle cell selection."""
        idx = evt.index
        if idx < len(notebook.cells):
            cell = notebook.cells[idx]
            cell_info = f"{'Code' if cell.type == CellType.CODE else 'Markdown'} Cell #{idx}"
            if cell.execution_count:
                cell_info += f" (executed: [{cell.execution_count}])"

            output_text = ""
            error_text = ""
            for output in cell.outputs:
                text = format_output(output)
                if output.get("type") == "error":
                    error_text += text + "\n"
                else:
                    output_text += text + "\n"

            # For markdown cells, show rendered preview
            md_preview = ""
            if cell.type == CellType.MARKDOWN and cell.source.strip():
                md_preview = cell.source

            return (
                cell_info,
                cell.source,
                output_text.strip(),
                error_text.strip(),
                md_preview,
            )
        return "", "", "", "", ""

    def execute_cell(cell_index_str, code):
        """Execute a single cell and return results."""
        # Parse index from the dropdown label
        try:
            cell_index = int(cell_index_str.split(":")[0])
        except (ValueError, IndexError):
            return "Select a cell first", "", get_cell_choices(), get_notebook_info()

        if cell_index >= len(notebook.cells):
            return "Cell not found", "", get_cell_choices(), get_notebook_info()

        cell = notebook.cells[cell_index]
        cell.source = code

        if cell.type == CellType.MARKDOWN:
            return "", "", get_cell_choices(), get_notebook_info()

        result = kernel.execute_cell(code)
        cell.outputs = result.outputs
        cell.execution_count = result.execution_count

        output_text = ""
        error_text = ""
        for output in result.outputs:
            text = format_output(output)
            if output.get("type") == "error":
                error_text += text + "\n"
            else:
                output_text += text + "\n"

        return (
            output_text.strip(),
            error_text.strip(),
            get_cell_choices(),
            get_notebook_info(),
        )

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
                    results.append(f"--- Cell {i} [OK] ---\n{output_text}")
                else:
                    results.append(f"--- Cell {i} [ERROR] ---\n{result.error}")
                    break

        return (
            "\n\n".join(results),
            get_cell_choices(),
            get_notebook_info(),
        )

    def add_cell(cell_type: str, position: str):
        """Add a new cell."""
        ct = CellType.CODE if cell_type == "code" else CellType.MARKDOWN
        cell = Cell(type=ct, source="")
        if position == "end":
            notebook.add_cell(cell)
        else:
            notebook.insert_cell(0, cell)
        return get_cell_choices(), get_notebook_info()

    def delete_cell(cell_index_str):
        """Delete a cell."""
        try:
            idx = int(cell_index_str.split(":")[0])
            if 0 <= idx < len(notebook.cells):
                notebook.remove_cell(idx)
        except (ValueError, IndexError):
            pass
        return get_cell_choices(), get_notebook_info()

    def move_cell_up(cell_index_str):
        """Move selected cell up."""
        try:
            idx = int(cell_index_str.split(":")[0])
            if 0 < idx < len(notebook.cells):
                notebook.cells[idx], notebook.cells[idx - 1] = (
                    notebook.cells[idx - 1],
                    notebook.cells[idx],
                )
        except (ValueError, IndexError):
            pass
        return get_cell_choices(), get_notebook_info()

    def move_cell_down(cell_index_str):
        """Move selected cell down."""
        try:
            idx = int(cell_index_str.split(":")[0])
            if 0 <= idx < len(notebook.cells) - 1:
                notebook.cells[idx], notebook.cells[idx + 1] = (
                    notebook.cells[idx + 1],
                    notebook.cells[idx],
                )
        except (ValueError, IndexError):
            pass
        return get_cell_choices(), get_notebook_info()

    def update_cell_source(cell_index_str, code):
        """Update a cell's source when editor changes."""
        try:
            idx = int(cell_index_str.split(":")[0])
            if 0 <= idx < len(notebook.cells):
                notebook.cells[idx].source = code
        except (ValueError, IndexError):
            pass
        return get_cell_choices()

    def save_notebook(include_session: bool):
        """Save notebook to file."""
        path = notebook.metadata.get("path", "notebook.nblr")
        if include_session:
            session_data = {
                "user_ns": kernel.get_namespace(),
                "execution_count": kernel.execution_count,
            }
            notebook.save(
                Path(path), include_session=True, session_data=session_data
            )
            session_manager.save_checkpoint(kernel, Path(path))
        else:
            notebook.save(Path(path))
        return f"Saved to {path}" + (" (with session)" if include_session else "")

    def load_notebook(file_path):
        """Load notebook from file."""
        nonlocal notebook
        if file_path:
            notebook = Notebook.load(Path(file_path.name))
            notebook.metadata["path"] = file_path.name
            return (
                get_cell_choices(),
                f"Loaded {file_path.name}",
                get_notebook_info(),
            )
        return get_cell_choices(), "No file selected", get_notebook_info()

    def get_variables():
        """Get all variables in namespace."""
        variables = kernel.get_defined_names()
        if not variables:
            return "No variables defined"

        lines = []
        for name in sorted(variables):
            value = kernel.get_variable(name)
            var_type = type(value).__name__
            val_repr = repr(value)
            if len(val_repr) > 80:
                val_repr = val_repr[:77] + "..."
            lines.append(f"  {name} : {var_type} = {val_repr}")

        return "\n".join(lines)

    def clear_variables():
        """Clear all variables."""
        kernel.reset()
        return "Kernel reset - all variables cleared"

    # Build Gradio interface
    custom_css = """
    .output-area { font-family: 'Fira Code', 'Consolas', monospace; }
    .error-area { color: #e74c3c; font-family: 'Fira Code', 'Consolas', monospace; }
    """

    with gr.Blocks(
        title="notebook-lr",
        theme=gr.themes.Soft(),
        css=custom_css,
    ) as demo:
        gr.Markdown("# notebook-lr")
        notebook_info = gr.Markdown(get_notebook_info())

        with gr.Row():
            # Left sidebar - cell list and operations
            with gr.Column(scale=1, min_width=280):
                gr.Markdown("### Cells")
                cell_list = gr.Dropdown(
                    choices=get_cell_choices(),
                    label="Select Cell",
                    interactive=True,
                )

                with gr.Row():
                    add_code_btn = gr.Button("+ Code", size="sm")
                    add_md_btn = gr.Button("+ Markdown", size="sm")

                with gr.Row():
                    move_up_btn = gr.Button("Move Up", size="sm")
                    move_down_btn = gr.Button("Move Down", size="sm")

                delete_btn = gr.Button("Delete Cell", variant="stop", size="sm")

            # Main area - editor and output
            with gr.Column(scale=3):
                cell_info_display = gr.Textbox(
                    label="Cell Info",
                    interactive=False,
                    max_lines=1,
                )
                code_input = gr.Code(
                    language="python",
                    label="Cell Source",
                    lines=12,
                )

                with gr.Row():
                    execute_btn = gr.Button(
                        "Run Cell",
                        variant="primary",
                        size="sm",
                    )
                    execute_all_btn = gr.Button(
                        "Run All Cells",
                        size="sm",
                    )

                with gr.Tabs():
                    with gr.Tab("Output"):
                        output_display = gr.TextArea(
                            label="Output",
                            lines=6,
                            interactive=False,
                            elem_classes=["output-area"],
                        )
                    with gr.Tab("Errors"):
                        error_display = gr.TextArea(
                            label="Errors",
                            lines=4,
                            interactive=False,
                            elem_classes=["error-area"],
                        )
                    with gr.Tab("Markdown Preview"):
                        md_preview = gr.Markdown("")

        with gr.Accordion("File Operations", open=False):
            with gr.Row():
                save_btn = gr.Button("Save")
                save_session_btn = gr.Button("Save with Session")
            load_file = gr.File(label="Load Notebook", file_types=[".nblr"])
            save_status = gr.Textbox(label="Status", interactive=False)

        with gr.Accordion("Session / Variables", open=False):
            with gr.Row():
                vars_btn = gr.Button("Show Variables")
                clear_btn = gr.Button("Clear Variables", variant="stop")
            vars_display = gr.TextArea(
                label="Namespace",
                lines=8,
                interactive=False,
                elem_classes=["output-area"],
            )

        with gr.Accordion("Keyboard Shortcuts (TUI)", open=False):
            gr.Markdown(
                "| Key | Action |\n"
                "|-----|--------|\n"
                "| `Enter` | Edit cell |\n"
                "| `e` | Execute cell |\n"
                "| `E` | Execute all |\n"
                "| `a` / `b` | Add cell after/before |\n"
                "| `d` | Delete cell |\n"
                "| `u` | Undo delete |\n"
                "| `j` / `k` | Navigate up/down |\n"
                "| `J` / `K` | Move cell up/down |\n"
                "| `c` | Duplicate cell |\n"
                "| `m` | Toggle code/markdown |\n"
                "| `s` / `S` | Save / Save with session |\n"
                "| `?` | Show variables |\n"
                "| `/` | Search cells |\n"
                "| `h` | Help |\n"
                "| `q` | Quit |"
            )

        # Event handlers
        cell_list.select(
            select_cell,
            outputs=[cell_info_display, code_input, output_display, error_display, md_preview],
        )

        execute_btn.click(
            execute_cell,
            inputs=[cell_list, code_input],
            outputs=[output_display, error_display, cell_list, notebook_info],
        )

        execute_all_btn.click(
            execute_all,
            outputs=[output_display, cell_list, notebook_info],
        )

        add_code_btn.click(
            lambda: add_cell("code", "end"),
            outputs=[cell_list, notebook_info],
        )

        add_md_btn.click(
            lambda: add_cell("markdown", "end"),
            outputs=[cell_list, notebook_info],
        )

        delete_btn.click(
            delete_cell,
            inputs=[cell_list],
            outputs=[cell_list, notebook_info],
        )

        move_up_btn.click(
            move_cell_up,
            inputs=[cell_list],
            outputs=[cell_list, notebook_info],
        )

        move_down_btn.click(
            move_cell_down,
            inputs=[cell_list],
            outputs=[cell_list, notebook_info],
        )

        code_input.change(
            update_cell_source,
            inputs=[cell_list, code_input],
            outputs=[cell_list],
        )

        save_btn.click(
            lambda: save_notebook(False),
            outputs=save_status,
        )

        save_session_btn.click(
            lambda: save_notebook(True),
            outputs=save_status,
        )

        load_file.change(
            load_notebook,
            inputs=load_file,
            outputs=[cell_list, save_status, notebook_info],
        )

        vars_btn.click(
            get_variables,
            outputs=vars_display,
        )

        clear_btn.click(
            clear_variables,
            outputs=vars_display,
        )

    demo.launch(share=share)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        nb = Notebook.load(Path(sys.argv[1]))
        launch_web(nb)
    else:
        launch_web()
