from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from mojimaru import __version__
from mojimaru.pipeline import translate_directory, translate_image
from mojimaru.protocol import SourceLang, TargetLang

console = Console()

SOURCE_CHOICES: tuple[SourceLang, ...] = ("ja", "zh", "ko", "auto")
TARGET_CHOICES: tuple[TargetLang, ...] = (
    "en",
    "id",
    "es",
    "fr",
    "de",
    "pt",
    "ru",
    "vi",
    "th",
)


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    help="Mojimaru — manga translation pipeline.",
)
@click.version_option(__version__, "-V", "--version", prog_name="mojimaru")
def main() -> None:
    pass


@main.command(help="Translate one image or a whole directory of images.")
@click.option(
    "--image",
    "image",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Translate a single image file.",
)
@click.option(
    "--in",
    "input_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Input directory of images for batch mode.",
)
@click.option(
    "--out",
    "output",
    type=click.Path(path_type=Path),
    required=True,
    help="Output file (single-image mode) or directory (batch mode).",
)
@click.option(
    "--source",
    type=click.Choice(SOURCE_CHOICES),
    default="auto",
    show_default=True,
    help="Source language.",
)
@click.option(
    "--target",
    type=click.Choice(TARGET_CHOICES),
    default="en",
    show_default=True,
    help="Target language.",
)
@click.option(
    "-r",
    "--recursive",
    is_flag=True,
    help="Recurse into subdirectories (batch mode only).",
)
def translate(
    image: Path | None,
    input_dir: Path | None,
    output: Path,
    source: SourceLang,
    target: TargetLang,
    recursive: bool,
) -> None:
    if image and input_dir:
        raise click.UsageError("Use either --image or --in, not both.")
    if not image and not input_dir:
        raise click.UsageError("Specify --image FILE or --in DIRECTORY.")

    if image:
        out_path = output if output.suffix else output / image.name
        with _progress() as progress:
            task = progress.add_task("translate", total=5)

            def on_progress(stage: str, current: int, total: int, note: str) -> None:
                progress.update(
                    task,
                    description=f"[bold]{stage}[/bold] {note}",
                    completed=min(progress.tasks[task].total or 5, current + 1),
                )

            translate_image(
                image,
                out_path,
                source=source,
                target=target,
                on_progress=on_progress,
            )
        console.print(f"[green]wrote[/green] {out_path}")
        return

    assert input_dir is not None
    if output.exists() and not output.is_dir():
        raise click.UsageError("--out must be a directory when using --in.")
    output.mkdir(parents=True, exist_ok=True)

    with _progress() as progress:
        task = progress.add_task("batch", total=None)

        def on_progress(stage: str, current: int, total: int, note: str) -> None:
            progress.update(
                task,
                total=total or None,
                completed=current,
                description=f"[bold]{stage}[/bold] {Path(note).name if note else ''}",
            )

        succeeded, failures = translate_directory(
            input_dir,
            output,
            source=source,
            target=target,
            recursive=recursive,
            on_progress=on_progress,
        )

    console.print(f"[green]succeeded[/green] {succeeded}")
    if failures:
        console.print(f"[red]failed[/red] {len(failures)}")
        for path, msg in failures:
            console.print(f"  {path}: {msg}")
        sys.exit(1)


@main.command(help="Run as a JSON sidecar (newline-delimited JSON over stdin/stdout).")
def serve() -> None:
    from mojimaru.sidecar import run

    run()


@main.command(help="Show version + which ML backends are importable.")
def info() -> None:
    from mojimaru.sidecar import _detect_backends

    backends = _detect_backends()
    console.print(f"mojimaru {__version__}")
    console.print(f"python   {sys.version.split()[0]}")
    console.print("backends:")
    for name, ok in backends.items():
        mark = "[green]ok[/green]" if ok else "[dim]missing[/dim]"
        console.print(f"  {name:<14} {mark}")


def _progress() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    )


if __name__ == "__main__":
    main()
