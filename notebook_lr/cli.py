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
from rich.rule import Rule
from rich.status import Status
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from notebook_lr import NotebookKernel, Notebook, Cell, CellType, SessionManager
from notebook_lr.file_watcher import FileWatcher
from notebook_lr.utils import format_output, format_rich_output, get_cell_type_icon, get_cell_status


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
        self._deleted_cells: list[tuple[int, Cell]] = []
        self._status_message = ""
        self.file_watcher: Optional[FileWatcher] = None

    def _set_message(self, message: str):
        """Set a status message to display on next render."""
        self._status_message = message

    def display_header(self):
        """Display the header with notebook info."""
        name = self.notebook.metadata.get("name", "Untitled")

        parts = []
        parts.append(f"[bold white]{name}[/bold white]")
        if self.modified:
            parts.append("[yellow]*modified[/yellow]")

        cell_count = len(self.notebook.cells)
        if cell_count > 0:
            parts.append(f"[dim]Cell {self.current_cell_index + 1}/{cell_count}[/dim]")
        else:
            parts.append("[dim]No cells[/dim]")

        executed = sum(1 for c in self.notebook.cells if c.execution_count is not None)
        if executed > 0:
            parts.append(f"[dim]{executed} executed[/dim]")

        header_text = "  |  ".join(parts)
        console.print(Panel(
            header_text,
            title="[bold blue]notebook-lr[/bold blue]",
            border_style="blue",
            padding=(0, 1),
        ))

    def display_cells(self):
        """Display all cells with current cell highlighted."""
        console.clear()
        self.display_header()

        if self._status_message:
            console.print(f"  {self._status_message}")
            self._status_message = ""

        if not self.notebook.cells:
            console.print()
            console.print(Panel(
                "[bold]Welcome to notebook-lr![/bold]\n\n"
                "This notebook is empty. Get started:\n"
                "  • Press [bold cyan]a[/bold cyan] to add a code cell\n"
                "  • Press [bold cyan]b[/bold cyan] to add a cell before\n"
                "  • Press [bold cyan]m[/bold cyan] to toggle code/markdown\n"
                "  • Press [bold cyan]h[/bold cyan] for all shortcuts\n\n"
                "[dim]Tip: Variables persist across cell executions.[/dim]",
                border_style="cyan",
                title="[bold blue]Getting Started[/bold blue]",
            ))
            return

        console.print()
        for i, cell in enumerate(self.notebook.cells):
            is_current = i == self.current_cell_index

            status_char, status_style = get_cell_status(cell)
            type_icon = get_cell_type_icon(cell.type)

            # Build cell title
            cursor = " > " if is_current else "   "

            if cell.type == CellType.CODE:
                exec_num = cell.execution_count or " "
                title_label = f"In [{exec_num}]"
            else:
                title_label = "Markdown"

            # Styling based on state
            if is_current:
                border_style = "bright_green"
                title_style = "bold bright_green"
            elif status_char == "err":
                border_style = "red"
                title_style = "red"
            elif status_char == "ok":
                border_style = "dim green"
                title_style = "dim green"
            else:
                border_style = "dim"
                title_style = "dim"

            # Status indicator
            if status_char == "ok":
                subtitle = "[green]ok[/green]"
            elif status_char == "err":
                subtitle = "[red]err[/red]"
            else:
                subtitle = None

            # Cell content
            if cell.type == CellType.CODE:
                if cell.source.strip():
                    try:
                        content = Syntax(
                            cell.source,
                            "python",
                            theme="monokai",
                            line_numbers=True,
                            word_wrap=True,
                        )
                    except Exception:
                        content = cell.source
                else:
                    content = Text("(empty)", style="dim italic")
            else:
                if cell.source.strip():
                    try:
                        content = Markdown(cell.source)
                    except Exception:
                        content = cell.source
                else:
                    content = Text("(empty)", style="dim italic")

            full_title = f"[{title_style}]{cursor}{type_icon}  {title_label}[/{title_style}]"

            panel = Panel(
                content,
                title=full_title,
                title_align="left",
                subtitle=subtitle,
                subtitle_align="right",
                border_style=border_style,
                padding=(0, 1),
            )
            console.print(panel)

            # Display outputs for code cells
            if cell.type == CellType.CODE and cell.outputs:
                for output in cell.outputs:
                    rich_output = format_rich_output(output)
                    if output.get("type") == "error":
                        console.print(Panel(
                            rich_output,
                            title="[red]Error[/red]",
                            title_align="left",
                            border_style="red",
                            padding=(0, 1),
                        ))
                    else:
                        out_label = f"Out [{cell.execution_count or ''}]"
                        console.print(Panel(
                            rich_output,
                            title=f"[blue]{out_label}[/blue]",
                            title_align="left",
                            border_style="blue",
                            padding=(0, 1),
                        ))

    def display_command_bar(self):
        """Display compact command bar at bottom."""
        console.print()
        console.print(Rule(style="dim"))

        commands = [
            ("Enter", "Edit"),
            ("e", "Run"),
            ("E", "RunAll"),
            ("a/b", "Add"),
            ("d", "Del"),
            ("u", "Undo"),
            ("m", "Type"),
            ("j/k", "Nav"),
            ("J/K", "Move"),
            ("c", "Copy"),
            ("s/S", "Save"),
            ("?", "Vars"),
            ("h", "Help"),
            ("q", "Quit"),
        ]

        bar = Text()
        for i, (key, action) in enumerate(commands):
            if i > 0:
                bar.append("  ", style="dim")
            bar.append(key, style="bold cyan")
            bar.append(f":{action}", style="dim")

        console.print(bar, justify="center")
        console.print(Rule(style="dim"))

    def edit_current_cell(self):
        """Open editor for current cell."""
        if not self.notebook.cells:
            self._set_message("[yellow]No cells to edit[/yellow]")
            return

        cell = self.notebook.get_cell(self.current_cell_index)
        type_icon = get_cell_type_icon(cell.type)

        console.print()
        console.print(f"[bold]Editing cell {self.current_cell_index} [{type_icon}][/bold]")

        # Show current content
        if cell.source.strip():
            console.print("[dim]Current content:[/dim]")
            if cell.type == CellType.CODE:
                console.print(Syntax(
                    cell.source, "python",
                    theme="monokai",
                    line_numbers=True,
                ))
            else:
                console.print(Panel(Markdown(cell.source), border_style="dim"))
            console.print()

        console.print("[dim]Enter new content (empty line to finish, 'cancel' to abort):[/dim]")

        lines = []
        line_num = 1
        while True:
            try:
                prompt_str = f"[green]{line_num:>3}[/green] | "
                line = console.input(prompt_str)
                if line.strip() == "cancel":
                    self._set_message("[yellow]Edit cancelled[/yellow]")
                    return
                if line == "" and lines:
                    break
                lines.append(line)
                line_num += 1
            except KeyboardInterrupt:
                self._set_message("[yellow]Edit cancelled[/yellow]")
                return

        if lines:
            new_source = "\n".join(lines)
            if new_source != cell.source:
                cell.source = new_source
                cell.outputs = []
                cell.execution_count = None
                self.modified = True
                self._set_message("[green]Cell updated[/green]")
            else:
                self._set_message("[dim]No changes[/dim]")

    def execute_current_cell(self):
        """Execute the current cell."""
        if not self.notebook.cells:
            self._set_message("[yellow]No cells to execute[/yellow]")
            return

        cell = self.notebook.get_cell(self.current_cell_index)

        if cell.type != CellType.CODE:
            self._set_message("[yellow]Cannot execute markdown cell[/yellow]")
            return

        if not cell.source.strip():
            self._set_message("[yellow]Cell is empty[/yellow]")
            return

        with Status(
            f"[bold]Executing cell {self.current_cell_index}...[/bold]",
            console=console,
            spinner="dots",
        ):
            result = self.kernel.execute_cell(cell.source)

        cell.outputs = result.outputs
        cell.execution_count = result.execution_count
        self.modified = True

        if result.success:
            self._set_message(f"[green]Cell {self.current_cell_index} executed[/green]")
        else:
            self._set_message(f"[red]Error in cell {self.current_cell_index}: {result.error}[/red]")

    def execute_all_cells(self):
        """Execute all cells in sequence with progress."""
        code_cells = [
            (i, c) for i, c in enumerate(self.notebook.cells)
            if c.type == CellType.CODE and c.source.strip()
        ]

        if not code_cells:
            self._set_message("[yellow]No code cells to execute[/yellow]")
            return

        console.print()
        success_count = 0
        error_count = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            console=console,
        ) as progress:
            task = progress.add_task("Executing cells...", total=len(code_cells))

            for i, cell in code_cells:
                progress.update(task, description=f"Cell {i}...")
                result = self.kernel.execute_cell(cell.source)
                cell.outputs = result.outputs
                cell.execution_count = result.execution_count

                if result.success:
                    success_count += 1
                else:
                    error_count += 1
                    progress.update(task, advance=1)
                    break

                progress.update(task, advance=1)

        self.modified = True

        if error_count > 0:
            self._set_message(
                f"[yellow]Executed {success_count} cells, {error_count} error(s)[/yellow]"
            )
        else:
            self._set_message(f"[green]All {success_count} cells executed[/green]")

        console.input("\n[dim]Press Enter to continue...[/dim]")

    def add_cell_after(self):
        """Add a new cell after current."""
        new_cell = Cell(type=CellType.CODE, source="")
        idx = self.current_cell_index + 1 if self.notebook.cells else 0
        self.notebook.insert_cell(idx, new_cell)
        self.current_cell_index = idx
        self.modified = True
        self._set_message(f"[green]Added code cell at position {idx}[/green]")

    def add_cell_before(self):
        """Add a new cell before current."""
        new_cell = Cell(type=CellType.CODE, source="")
        idx = self.current_cell_index if self.notebook.cells else 0
        self.notebook.insert_cell(idx, new_cell)
        self.modified = True
        self._set_message(f"[green]Added code cell at position {idx}[/green]")

    def delete_current_cell(self):
        """Delete current cell with undo support."""
        if not self.notebook.cells:
            self._set_message("[yellow]No cells to delete[/yellow]")
            return

        if Confirm.ask(f"Delete cell {self.current_cell_index}?"):
            cell = self.notebook.remove_cell(self.current_cell_index)
            self._deleted_cells.append((self.current_cell_index, cell))
            if self.current_cell_index >= len(self.notebook.cells):
                self.current_cell_index = max(0, len(self.notebook.cells) - 1)
            self.modified = True
            self._set_message("[green]Cell deleted[/green] [dim](press 'u' to undo)[/dim]")

    def undo_delete(self):
        """Undo the last cell deletion."""
        if not self._deleted_cells:
            self._set_message("[yellow]Nothing to undo[/yellow]")
            return

        index, cell = self._deleted_cells.pop()
        index = min(index, len(self.notebook.cells))
        self.notebook.insert_cell(index, cell)
        self.current_cell_index = index
        self.modified = True
        self._set_message("[green]Cell restored[/green]")

    def move_cell_up(self):
        """Move current cell up."""
        if not self.notebook.cells or self.current_cell_index == 0:
            self._set_message("[yellow]Cannot move up[/yellow]")
            return

        i = self.current_cell_index
        self.notebook.cells[i], self.notebook.cells[i - 1] = (
            self.notebook.cells[i - 1],
            self.notebook.cells[i],
        )
        self.current_cell_index -= 1
        self.modified = True
        self._set_message("[green]Cell moved up[/green]")

    def move_cell_down(self):
        """Move current cell down."""
        if not self.notebook.cells or self.current_cell_index >= len(self.notebook.cells) - 1:
            self._set_message("[yellow]Cannot move down[/yellow]")
            return

        i = self.current_cell_index
        self.notebook.cells[i], self.notebook.cells[i + 1] = (
            self.notebook.cells[i + 1],
            self.notebook.cells[i],
        )
        self.current_cell_index += 1
        self.modified = True
        self._set_message("[green]Cell moved down[/green]")

    def duplicate_cell(self):
        """Duplicate the current cell."""
        if not self.notebook.cells:
            self._set_message("[yellow]No cells to duplicate[/yellow]")
            return

        cell = self.notebook.get_cell(self.current_cell_index)
        new_cell = Cell(
            type=cell.type,
            source=cell.source,
            metadata=cell.metadata.copy(),
        )
        self.notebook.insert_cell(self.current_cell_index + 1, new_cell)
        self.current_cell_index += 1
        self.modified = True
        self._set_message("[green]Cell duplicated[/green]")

    def clear_outputs(self):
        """Clear all cell outputs."""
        cleared = 0
        for cell in self.notebook.cells:
            if cell.outputs or cell.execution_count is not None:
                cleared += 1
            cell.outputs = []
            cell.execution_count = None
        if cleared:
            self.modified = True
            self._set_message(f"[green]Cleared outputs from {cleared} cells[/green]")
        else:
            self._set_message("[dim]No outputs to clear[/dim]")

    def clear_kernel(self):
        """Reset the kernel."""
        if Confirm.ask("Clear all variables and reset kernel?"):
            self.kernel.reset()
            self._set_message("[green]Kernel reset[/green]")

    def toggle_cell_type(self):
        """Toggle between code and markdown."""
        if not self.notebook.cells:
            self._set_message("[yellow]No cells[/yellow]")
            return

        cell = self.notebook.get_cell(self.current_cell_index)
        cell.type = CellType.MARKDOWN if cell.type == CellType.CODE else CellType.CODE
        cell.outputs = []
        cell.execution_count = None
        self.modified = True
        self._set_message(f"[green]Cell type: {cell.type.value}[/green]")

    def save_notebook(self, include_session: bool = False):
        """Save notebook to file."""
        path = Path(self.notebook.metadata.get("path", ""))

        if not path or str(path) == "." or not path.suffix:
            path_str = Prompt.ask("Enter file path", default="notebook.nblr")
            path = Path(path_str)

        if include_session:
            session_data = {
                "user_ns": self.kernel.get_namespace(),
                "execution_count": self.kernel.execution_count,
            }
            self.notebook.save(path, include_session=True, session_data=session_data)
            self.session_manager.save_checkpoint(self.kernel, path)
        else:
            self.notebook.save(path)

        self.notebook.metadata["path"] = str(path)
        self.modified = False

        msg = f"[green]Saved to {path}[/green]"
        if include_session:
            msg += " [dim](with session)[/dim]"
        self._set_message(msg)

    def load_session(self):
        """Load a saved session."""
        sessions = self.session_manager.list_sessions()

        if not sessions:
            self._set_message("[yellow]No saved sessions found[/yellow]")
            return

        console.print()
        table = Table(title="Saved Sessions", border_style="blue")
        table.add_column("#", style="bold cyan", justify="right")
        table.add_column("Name", style="white")
        table.add_column("Saved At", style="dim")
        table.add_column("Variables", justify="right")

        for i, session in enumerate(sessions):
            table.add_row(
                str(i),
                session.get("name", ""),
                session.get("saved_at", ""),
                str(session.get("var_count", 0)),
            )

        console.print(table)

        choice = Prompt.ask("Select session number (or 'cancel')", default="0")
        if choice == "cancel":
            self._set_message("[yellow]Cancelled[/yellow]")
            return

        try:
            idx = int(choice)
            if 0 <= idx < len(sessions):
                path = Path(sessions[idx]["path"])
                info = self.session_manager.load_session(self.kernel, path)
                msg = f"[green]Loaded session with {len(info['restored_vars'])} variables[/green]"
                if info.get("unpicklable_vars"):
                    msg += f"\n  [yellow]Could not restore: {', '.join(info['unpicklable_vars'])}[/yellow]"
                self._set_message(msg)
            else:
                self._set_message("[red]Invalid selection[/red]")
        except ValueError:
            self._set_message("[red]Invalid selection[/red]")

    def show_variables(self):
        """Show current variables in namespace."""
        variables = self.kernel.get_defined_names()

        if not variables:
            console.print("\n[yellow]No variables defined[/yellow]")
            console.input("\n[dim]Press Enter to continue...[/dim]")
            return

        console.print()
        table = Table(
            title="Namespace Variables",
            border_style="cyan",
            show_lines=True,
        )
        table.add_column("Name", style="bold cyan", no_wrap=True)
        table.add_column("Type", style="yellow")
        table.add_column("Value", max_width=60, overflow="ellipsis")

        for name in sorted(variables):
            value = self.kernel.get_variable(name)
            var_type = type(value).__name__
            try:
                var_str = repr(value)
                if len(var_str) > 60:
                    var_str = var_str[:57] + "..."
            except Exception:
                var_str = "<unable to repr>"
            table.add_row(name, var_type, var_str)

        console.print(table)
        console.input("\n[dim]Press Enter to continue...[/dim]")

    def search_cells(self):
        """Search cells by content."""
        console.print()
        term = Prompt.ask("[cyan]Search[/cyan]")
        if not term:
            return

        matches = []
        for i, cell in enumerate(self.notebook.cells):
            if term.lower() in cell.source.lower():
                matches.append(i)

        if not matches:
            self._set_message(f"[yellow]No matches for '{term}'[/yellow]")
            return

        if len(matches) == 1:
            self.current_cell_index = matches[0]
            self._set_message(f"[green]Found in cell {matches[0]}[/green]")
        else:
            console.print(f"\n[cyan]Found in {len(matches)} cells:[/cyan]")
            for idx in matches:
                cell = self.notebook.cells[idx]
                preview = cell.source[:60].replace("\n", " ")
                console.print(f"  [{idx}] {preview}...")

            choice = Prompt.ask("Go to cell", default=str(matches[0]))
            try:
                target = int(choice)
                if 0 <= target < len(self.notebook.cells):
                    self.current_cell_index = target
            except ValueError:
                pass

    def show_help(self):
        """Show detailed help."""
        console.print()

        help_sections = [
            ("Navigation", [
                ("j / down", "Next cell"),
                ("k / up", "Previous cell"),
                ("g", "First cell"),
                ("G", "Last cell"),
            ]),
            ("Cell Editing", [
                ("Enter", "Edit current cell"),
                ("e", "Execute current cell"),
                ("E", "Execute all cells"),
                ("a", "Add cell after current"),
                ("b", "Add cell before current"),
                ("d", "Delete current cell"),
                ("u", "Undo last delete"),
                ("m", "Toggle code/markdown"),
                ("c", "Duplicate cell"),
            ]),
            ("Cell Reordering", [
                ("J", "Move cell down"),
                ("K", "Move cell up"),
            ]),
            ("File & Session", [
                ("s", "Save notebook"),
                ("S", "Save with session state"),
                ("l", "Load saved session"),
            ]),
            ("Inspect & Tools", [
                ("?", "Show variables"),
                ("/", "Search cells"),
                ("x", "Clear all outputs"),
                ("X", "Reset kernel"),
            ]),
            ("General", [
                ("h", "Show this help"),
                ("q", "Quit"),
            ]),
        ]

        for section_name, bindings in help_sections:
            table = Table(
                show_header=False,
                box=None,
                padding=(0, 2),
                title=f"[bold]{section_name}[/bold]",
                title_justify="left",
            )
            table.add_column("Key", style="bold cyan", no_wrap=True, min_width=12)
            table.add_column("Action")
            for key, action in bindings:
                table.add_row(key, action)
            console.print(table)
            console.print()

        console.print("[dim]Tip: Variables persist across cell executions.[/dim]")
        console.print("[dim]Tip: Save with session (S) to resume later with all variables.[/dim]")
        console.print()
        console.input("[dim]Press Enter to continue...[/dim]")

    def run(self):
        """Run the interactive editor."""
        # Check for saved session
        notebook_path = self.notebook.metadata.get("path")
        if notebook_path and Path(notebook_path).exists():
            checkpoint_info = self.session_manager.load_checkpoint(
                self.kernel, Path(notebook_path)
            )
            if checkpoint_info:
                self._set_message(
                    f"[green]Restored session with "
                    f"{len(checkpoint_info['restored_vars'])} variables[/green]"
                )

        while self.running:
            self.display_cells()
            self.display_command_bar()

            try:
                key = console.input("\n[bold cyan]> [/bold cyan]").strip()
            except (KeyboardInterrupt, EOFError):
                key = "q"

            if key == "q":
                if self.modified:
                    if Confirm.ask("Save before quitting?"):
                        self.save_notebook()
                self.running = False

            elif key == "h":
                self.show_help()

            elif key == "" or key == "enter":
                self.edit_current_cell()

            elif key == "e":
                self.execute_current_cell()

            elif key == "E":
                self.execute_all_cells()

            elif key == "a":
                self.add_cell_after()

            elif key == "b":
                self.add_cell_before()

            elif key == "d":
                self.delete_current_cell()

            elif key == "u":
                self.undo_delete()

            elif key == "m":
                self.toggle_cell_type()

            elif key == "c":
                self.duplicate_cell()

            elif key == "s":
                self.save_notebook()

            elif key == "S":
                self.save_notebook(include_session=True)

            elif key == "l":
                self.load_session()

            elif key == "?":
                self.show_variables()

            elif key == "/":
                self.search_cells()

            elif key == "x":
                self.clear_outputs()

            elif key == "X":
                self.clear_kernel()

            elif key in ("j", "down"):
                if self.notebook.cells and self.current_cell_index < len(self.notebook.cells) - 1:
                    self.current_cell_index += 1

            elif key in ("k", "up"):
                if self.current_cell_index > 0:
                    self.current_cell_index -= 1

            elif key == "g":
                self.current_cell_index = 0

            elif key == "G":
                if self.notebook.cells:
                    self.current_cell_index = len(self.notebook.cells) - 1

            elif key == "J":
                self.move_cell_down()

            elif key == "K":
                self.move_cell_up()

            else:
                self._set_message(f"[dim]Unknown command: '{key}' (press 'h' for help)[/dim]")

        console.print("\n[green]Goodbye![/green]")


@click.group()
def main():
    """notebook-lr: A Jupyter-like notebook system with persistent session context."""
    pass


@main.command()
@click.argument("path", type=click.Path(), default="notebook.nblr")
@click.option("--name", "-n", default=None, help="Notebook name")
def new(path: str, name: str):
    """Create a new notebook."""
    if name is None:
        name = Path(path).stem

    nb = Notebook.new(name=name)
    nb.metadata["path"] = path
    nb.add_cell(
        type=CellType.CODE,
        source="# Welcome to notebook-lr!\n# Start writing Python code here.\n",
    )
    nb.add_cell(
        type=CellType.MARKDOWN,
        source="## Notes\n\nAdd your notes here.",
    )
    nb.save(Path(path))

    console.print(Panel(
        f"[green]Created:[/green] {path}\n"
        f"[dim]Name:[/dim] {name}\n"
        f"[dim]Cells:[/dim] 2 (1 code, 1 markdown)",
        title="[bold blue]notebook-lr[/bold blue]",
        border_style="green",
    ))
    console.print(f"\n[dim]Edit with:[/dim] notebook-lr edit {path}")


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

    nb_name = nb.metadata.get("name", Path(path).stem)
    console.print(Panel(
        f"[bold]{nb_name}[/bold]  [dim]{path}[/dim]",
        title="[bold blue]notebook-lr[/bold blue]",
        border_style="blue",
    ))
    console.print()

    code_cells = [
        (i, c) for i, c in enumerate(nb.cells)
        if c.type == CellType.CODE and c.source.strip()
    ]

    if not code_cells:
        console.print("[yellow]No code cells to execute[/yellow]")
        return

    success_count = 0
    for cell_idx, cell in code_cells:
        console.print(f"[dim]--- Cell {cell_idx} ---[/dim]")
        console.print(Syntax(cell.source, "python", theme="monokai", line_numbers=True))

        with Status("Executing...", console=console, spinner="dots"):
            result = kernel.execute_cell(cell.source)

        cell.outputs = result.outputs
        cell.execution_count = result.execution_count

        if result.success:
            success_count += 1
            for output in result.outputs:
                rich_out = format_rich_output(output)
                if output.get("type") != "error":
                    console.print(rich_out)
        else:
            console.print(f"[red]Error: {result.error}[/red]")
            break

        console.print()

    if save_session:
        session_manager = SessionManager()
        session_manager.save_checkpoint(kernel, Path(path))
        console.print("[dim]Session saved[/dim]")

    nb.save(Path(path))

    total = len(code_cells)
    if success_count == total:
        console.print(f"[green]All {total} cells executed successfully[/green]")
    else:
        console.print(f"[yellow]Executed {success_count}/{total} cells[/yellow]")


@main.command()
def sessions():
    """List saved sessions."""
    sm = SessionManager()
    sessions_list = sm.list_sessions()

    if not sessions_list:
        console.print("[yellow]No saved sessions found[/yellow]")
        console.print("[dim]Save a session with 'S' in the editor, or --save-session when running[/dim]")
        return

    table = Table(
        title="Saved Sessions",
        border_style="blue",
        show_lines=True,
    )
    table.add_column("#", style="bold cyan", justify="right")
    table.add_column("Name", style="white")
    table.add_column("Saved At", style="dim")
    table.add_column("Variables", justify="right", style="green")

    for i, session in enumerate(sessions_list):
        table.add_row(
            str(i),
            session.get("name", ""),
            session.get("saved_at", ""),
            str(session.get("var_count", 0)),
        )

    console.print(table)


@main.command()
@click.argument("path", type=click.Path(exists=True), required=False, default=None)
def web(path: str):
    """Launch web interface for a notebook.

    If PATH is given, opens that notebook. Otherwise starts with a new empty notebook.
    """
    try:
        from notebook_lr.web import launch_web
        if path:
            nb = Notebook.load(Path(path))
        else:
            nb = None
        launch_web(nb)
    except ImportError:
        console.print("[red]Web interface requires flask. Install with: pip install flask[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
