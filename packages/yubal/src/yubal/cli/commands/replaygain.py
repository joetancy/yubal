"""ReplayGain library rescan command."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from yubal.services.replaygain import ReplayGainService


def replaygain_rescan_cmd(
    library: Annotated[
        Path,
        typer.Argument(
            metavar="LIBRARY",
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
            help="Root directory of the music library.",
        ),
    ],
    loudness: Annotated[
        int,
        typer.Option(
            "--loudness",
            min=-30,
            max=0,
            help="ReplayGain target loudness in LUFS.",
        ),
    ] = -14,
    threads: Annotated[
        str,
        typer.Option(
            "--threads",
            help='Number of rsgain workers, or "MAX".',
        ),
    ] = "MAX",
    no_album: Annotated[
        bool,
        typer.Option(
            "--no-album",
            help="Write track gain only; do not calculate album gain.",
        ),
    ] = False,
) -> None:
    """Recalculate ReplayGain tags for every supported track in a library.

    Existing ReplayGain tags are recalculated. Audio data is not modified;
    rsgain writes loudness metadata tags only.
    """
    console = Console()
    service = ReplayGainService()

    console.print(
        f"Rescanning ReplayGain at {loudness} LUFS: [cyan]{library}[/cyan]"
    )
    success = service.rescan_library(
        library,
        loudness=loudness,
        threads=threads,
        album_mode=not no_album,
    )
    if not success:
        console.print("[red]ReplayGain rescan failed.[/red]")
        raise typer.Exit(code=1)

    console.print("[green]ReplayGain rescan complete.[/green]")
