"""
CLI interface for notebook-lr with Rich TUI.
"""

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.text import Text
from rich.layout import Layout
from rich.live import Live

from notebook_lr import NotebookKernel, Notebook, Cell, CellType, SessionManager
from notebook_lr.utils import format_output, truncate_text


console = Console()


class NotebookEditor:
    """Interactive notebook editor with Rich TUI."""

    def __init__(self, notebook: Notebook, kernel: Optional[NotebookKernel] = None):
        self.notebook = notebook
        self.kernel = kernel or NotebookKernel()
        self.session_manager = SessionManager()
        self.current_cell_index = 0
        self.running = True
        self.modified = False

    def display_header(self):
        """Display the header with notebook info."""
        name = self.notebook.metadata.get("name", "Untitled")
        modified_marker = " [yellow]*[/yellow]" if self.modified else ""
        console.print(Panel(f"[bold blue]{name}[/bold blue]{modified_marker}", title="notebook-lr"))

    def display_cells(self):
        """Display all cells with current cell highlighted."""
        console.clear()
        self.display_header()

        for i, cell in enumerate(self.notebook.cells):
            is_current = i == self.current_cell_index
            border_style = "green" if is_current else "dim"
            title_style = "bold green" if is_current else "dim"

            if cell.type == CellType.CODE:
                # Code cell
                title = f"[{title_style}]In [{cell.execution_count or ' '}][/{title_style}]"
                try:
                    content = Syntax(cell.source, "python", theme="monokai", line_numbers=False)
                except Exception:
                    content = cell.source

                panel = Panel(
                    content,
                    title=title,
                    border_style=border_style,
                    padding=(0, 1),
                )
            else:
                # Markdown cell
                title = f"[{title_style}]Markdown[/{title_style}]"
                try:
                    content = Markdown(cell.source)
                except Exception:
                    content = cell.source

                panel = Panel(
                    content,
                    title=title,
                    border_style=border_style,
                    padding=(0, 1),
                )

            console.print(panel)

            # Display outputs for code cells
            if cell.type == CellType.CODE and cell.outputs:
                for output in cell.outputs:
                    output_text = format_output(output)
                    if output.get("type") == "error":
                        console.print(Panel(output_text, border_style="red", title="Error"))
                    else:
                        console.print(Panel(output_text, border_style="blue", title="Out"))

    def display_commands(self):
        """Display available commands."""
        commands = Table(show_header=False, box=None)
        commands.add_column("Key", style="cyan")
        commands.add_column("Action")

        commands.add_row("[Enter]", "Edit current cell")
        commands.add_row("[e]", "Execute current cell")
        commands.add_row("[E]", "Execute all cells")
        commands.add_row("[a]", "Add cell after")
        commands.add_row("[b]", "Add cell before")
        commands.add_row("[d]", "Delete current cell")
        commands.add_row("[m]", "Toggle markdown/code")
        commands.add_row("[s]", "Save notebook")
        commands.add_row("[S]", "Save with session")
        commands.add_row("[l]", "Load session")
        commands.add_row("[j/k]", "Navigate cells")
        commands.add_row("[?]", "Show variables")
        commands.add_row("[q]", "Quit")
        commands.add_row("[h]", "Show help")

        console.print(Panel(commands, title="Commands", border_style="dim"))

    def edit_current_cell(self):
        """Open editor for current cell."""
        cell = self.notebook.get_cell(self.current_cell_index)

        # Use simple input for now (could use textual for better editor)
        console.print(f"\n[bold]Editing cell {self.current_cell_index}[/bold]")
        console.print("[dim]Enter code (empty line to finish, 'cancel' to abort)[/dim]")
        console.print()

        lines = []
        while True:
            try:
                line = Prompt.ask(">>> ")
                if line == "cancel":
                    return
                if line == "" and lines:
                    break
                lines.append(line)
            except KeyboardInterrupt:
                return

        new_source = "\n".join(lines)
        if new_source != cell.source:
            cell.source = new_source
            self.modified = True

    def execute_current_cell(self):
        """Execute the current cell."""
        cell = self.notebook.get_cell(self.current_cell_index)

        if cell.type != CellType.CODE:
            console.print("[yellow]Cannot execute markdown cell[/yellow]")
            return

        if not cell.source.strip():
            console.print("[yellow]Cell is empty[/yellow]")
            return

        console.print(f"\n[bold]Executing cell {self.current_cell_index}...[/bold]")

        result = self.kernel.execute_cell(cell.source)

        # Update cell with results
        cell.outputs = result.outputs
        cell.execution_count = result.execution_count

        self.modified = True

        # Display result
        if result.success:
            console.print("[green]✓ Success[/green]")
        else:
            console.print(f"[red]✗ Error: {result.error}[/red]")

    def execute_all_cells(self):
        """Execute all cells in sequence."""
        console.print("\n[bold]Executing all cells...[/bold]")

        for i, cell in enumerate(self.notebook.cells):
            if cell.type == CellType.CODE and cell.source.strip():
                self.current_cell_index = i
                self.execute_current_cell()

        console.print("[green]All cells executed[/green]")

    def add_cell_after(self):
        """Add a new cell after current."""
        new_cell = Cell(type=CellType.CODE, source="")
        self.notebook.insert_cell(self.current_cell_index + 1, new_cell)
        self.current_cell_index += 1
        self.modified = True
        console.print(f"[green]Added cell after position {self.current_cell_index - 1}[/green]")

    def add_cell_before(self):
        """Add a new cell before current."""
        new_cell = Cell(type=CellType.CODE, source="")
        self.notebook.insert_cell(self.current_cell_index, new_cell)
        self.modified = True
        console.print(f"[green]Added cell at position {self.current_cell_index}[/green]")

    def delete_current_cell(self):
        """Delete current cell."""
        if len(self.notebook.cells) == 0:
            console.print("[yellow]No cells to delete[/yellow]")
            return

        if Confirm.ask(f"Delete cell {self.current_cell_index}?"):
            self.notebook.remove_cell(self.current_cell_index)
            if self.current_cell_index >= len(self.notebook.cells):
                self.current_cell_index = max(0, len(self.notebook.cells) - 1)
            self.modified = True
            console.print("[green]Cell deleted[/green]")

    def toggle_cell_type(self):
        """Toggle between code and markdown."""
        cell = self.notebook.get_cell(self.current_cell_index)
        cell.type = CellType.MARKDOWN if cell.type == CellType.CODE else CellType.CODE
        self.modified = True
        console.print(f"[green]Cell type changed to {cell.type.value}[/green]")

    def save_notebook(self, include_session: bool = False):
        """Save notebook to file."""
        path = Path(self.notebook.metadata.get("path", ""))

        if not path or not path.exists():
            path = Prompt.ask("Enter file path", default="notebook.nblr")

        path = Path(path)

        if include_session:
            session_data = {
                "user_ns": self.kernel.get_namespace(),
                "execution_count": self.kernel.execution_count,
            }
            self.notebook.save(path, include_session=True, session_data=session_data)
            # Also save checkpoint
            self.session_manager.save_checkpoint(self.kernel, path)
        else:
            self.notebook.save(path)

        self.notebook.metadata["path"] = str(path)
        self.modified = False
        console.print(f"[green]Saved to {path}[/green]")

    def load_session(self):
        """Load a saved session."""
        sessions = self.session_manager.list_sessions()

        if not sessions:
            console.print("[yellow]No saved sessions found[/yellow]")
            return

        table = Table(title="Saved Sessions")
        table.add_column("#", style="cyan")
        table.add_column("Name")
        table.add_column("Saved At")
        table.add_column("Variables")

        for i, session in enumerate(sessions):
            table.add_row(
                str(i),
                session.get("name", ""),
                session.get("saved_at", ""),
                str(session.get("var_count", 0)),
            )

        console.print(table)

        choice = Prompt.ask("Select session number", default="0")
        try:
            idx = int(choice)
            if 0 <= idx < len(sessions):
                path = Path(sessions[idx]["path"])
                info = self.session_manager.load_session(self.kernel, path)
                console.print(f"[green]Loaded session with {len(info['restored_vars'])} variables[/green]")
                if info.get("unpicklable_vars"):
                    console.print(f"[yellow]Could not restore: {', '.join(info['unpicklable_vars'])}[/yellow]")
        except (ValueError, IndexError):
            console.print("[red]Invalid selection[/red]")

    def show_variables(self):
        """Show current variables in namespace."""
        variables = self.kernel.get_defined_names()

        if not variables:
            console.print("[yellow]No variables defined[/yellow]")
            return

        table = Table(title="Variables")
        table.add_column("Name", style="cyan")
        table.add_column("Type")
        table.add_column("Value", max_width=50)

        for name in sorted(variables):
            value = self.kernel.get_variable(name)
            var_type = type(value).__name__
            var_str = truncate_text(repr(value), 50)
            table.add_row(name, var_type, var_str)

        console.print(table)

    def show_help(self):
        """Show detailed help."""
        help_text = """
# notebook-lr Help

## Navigation
- **j/k** or **Up/Down**: Move between cells
- **g**: Go to first cell
- **G**: Go to last cell

## Cell Operations
- **Enter**: Edit current cell
- **e**: Execute current cell
- **E**: Execute all cells
- **a**: Add cell after current
- **b**: Add cell before current
- **d**: Delete current cell
- **m**: Toggle cell type (code/markdown)

## File Operations
- **s**: Save notebook
- **S**: Save with session state
- **l**: Load saved session
- **r**: Reload notebook from disk

## Session
- **?**: Show variables in namespace
- **x**: Clear all variables

## Other
- **h**: Show this help
- **q**: Quit

## Tips
- Variables persist across cell executions
- Save with session to resume later with all variables intact
- Use checkpoints for auto-recovery
"""
        console.print(Panel(Markdown(help_text), title="Help", border_style="blue"))

    def run(self):
        """Run the interactive editor."""
        # Check for saved session
        notebook_path = self.notebook.metadata.get("path")
        if notebook_path and Path(notebook_path).exists():
            checkpoint_info = self.session_manager.load_checkpoint(self.kernel, Path(notebook_path))
            if checkpoint_info:
                console.print(f"[green]Restored session with {len(checkpoint_info['restored_vars'])} variables[/green]")

        while self.running:
            self.display_cells()
            self.display_commands()

            try:
                key = console.input("\n[bold cyan]Press key (h for help): [/bold cyan]").strip().lower()
            except (KeyboardInterrupt, EOFError):
                key = "q"

            if key == "q":
                if self.modified:
                    if Confirm.ask("Save before quitting?"):
                        self.save_notebook()
                self.running = False

            elif key == "h":
                self.show_help()
                console.input("\n[dim]Press Enter to continue...[/dim]")

            elif key == "enter" or key == "":
                self.edit_current_cell()

            elif key == "e":
                self.execute_current_cell()
                console.input("\n[dim]Press Enter to continue...[/dim]")

            elif key == "e!" or key == "shift+e":
                self.execute_all_cells()
                console.input("\n[dim]Press Enter to continue...[/dim]")

            elif key == "a":
                self.add_cell_after()

            elif key == "b":
                self.add_cell_before()

            elif key == "d":
                self.delete_current_cell()

            elif key == "m":
                self.toggle_cell_type()

            elif key == "s":
                self.save_notebook()
                console.input("\n[dim]Press Enter to continue...[/dim]")

            elif key == "s!" or key == "shift+s":
                self.save_notebook(include_session=True)
                console.input("\n[dim]Press Enter to continue...[/dim]")

            elif key == "l":
                self.load_session()
                console.input("\n[dim]Press Enter to continue...[/dim]")

            elif key == "?":
                self.show_variables()
                console.input("\n[dim]Press Enter to continue...[/dim]")

            elif key in ("j", "down"):
                if self.current_cell_index < len(self.notebook.cells) - 1:
                    self.current_cell_index += 1

            elif key in ("k", "up"):
                if self.current_cell_index > 0:
                    self.current_cell_index -= 1

            elif key == "g":
                self.current_cell_index = 0

            elif key == "G":
                self.current_cell_index = max(0, len(self.notebook.cells) - 1)

        console.print("[green]Goodbye![/green]")


@click.group()
def main():
    """notebook-lr: A Jupyter-like notebook system with persistent session context."""
    pass


@main.command()
@click.argument("path", type=click.Path(), default="notebook.nblr")
def new(path: str):
    """Create a new notebook."""
    nb = Notebook.new(name=Path(path).stem)
    nb.metadata["path"] = path
    nb.add_cell(type=CellType.CODE, source="# Welcome to notebook-lr!\n")
    nb.save(Path(path))
    console.print(f"[green]Created new notebook: {path}[/green]")


@main.command()
@click.argument("path", type=click.Path(exists=True))
def edit(path: str):
    """Edit a notebook with the interactive TUI."""
    nb = Notebook.load(Path(path))
    nb.metadata["path"] = path

    editor = NotebookEditor(nb)
    editor.run()


@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--save-session", "-s", is_flag=True, help="Save session state after execution")
def run(path: str, save_session: bool):
    """Run a notebook non-interactively."""
    nb = Notebook.load(Path(path))
    kernel = NotebookKernel()

    console.print(f"[bold]Running notebook: {path}[/bold]\n")

    for i, cell in enumerate(nb.cells):
        if cell.type == CellType.CODE and cell.source.strip():
            console.print(f"[dim]Cell {i}:[/dim]")
            console.print(Syntax(cell.source, "python", theme="monokai"))

            result = kernel.execute_cell(cell.source)
            cell.outputs = result.outputs
            cell.execution_count = result.execution_count

            if result.success:
                for output in result.outputs:
                    console.print(format_output(output))
            else:
                console.print(f"[red]Error: {result.error}[/red]")
                break

            console.print()

    if save_session:
        session_manager = SessionManager()
        session_manager.save_checkpoint(kernel, Path(path))

    nb.save(Path(path))
    console.print("[green]Notebook execution complete[/green]")


@main.command()
def sessions():
    """List saved sessions."""
    sm = SessionManager()
    sessions_list = sm.list_sessions()

    if not sessions_list:
        console.print("[yellow]No saved sessions found[/yellow]")
        return

    table = Table(title="Saved Sessions")
    table.add_column("Name", style="cyan")
    table.add_column("Saved At")
    table.add_column("Variables")

    for session in sessions_list:
        table.add_row(
            session.get("name", ""),
            session.get("saved_at", ""),
            str(session.get("var_count", 0)),
        )

    console.print(table)


@main.command()
@click.argument("path", type=click.Path(exists=True))
def web(path: str):
    """Launch web interface for a notebook."""
    try:
        from notebook_lr.web import launch_web
        nb = Notebook.load(Path(path))
        launch_web(nb)
    except ImportError:
        console.print("[red]Web interface requires gradio. Install with: pip install gradio[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
