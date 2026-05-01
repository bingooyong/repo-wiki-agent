from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

_console = Console()


def get_console() -> Console:
    return _console


def info(message: str) -> None:
    _console.print(f"[cyan]INFO[/cyan] {message}")


def warn(message: str) -> None:
    _console.print(f"[yellow]WARN[/yellow] {message}")


def error(message: str) -> None:
    _console.print(f"[red]ERROR[/red] {message}")


@contextmanager
def task_progress(description: str) -> Iterator[Progress]:
    progress = Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        transient=True,
        console=_console,
    )
    with progress:
        progress.add_task(description=description, total=None)
        yield progress
