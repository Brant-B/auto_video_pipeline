"""Command line interface for auto_video_pipeline."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional

import typer
from rich.console import Console

from .config import build_pipeline_config
from .pipeline import run_pipeline

console = Console()
app = typer.Typer(add_completion=False, help="Auto Video Pipeline CLI")


def _gather_overrides(
    job_name: Optional[str],
    footage_glob: Optional[str],
    music_manifest: Optional[str],
    target_duration: Optional[int],
    transition: Optional[str],
    export_resolution: Optional[str],
    export_fps: Optional[int],
) -> Dict[str, str | int]:
    overrides: Dict[str, str | int] = {}
    if job_name:
        overrides["job.name"] = job_name
    if footage_glob:
        overrides["inputs.footage_glob"] = footage_glob
    if music_manifest:
        overrides["inputs.music_manifest"] = music_manifest
    if target_duration:
        overrides["timeline.target_duration_s"] = target_duration
    if transition:
        overrides["timeline.transition"] = transition
    if export_resolution:
        overrides["export.resolution"] = export_resolution
    if export_fps:
        overrides["export.fps"] = export_fps
    return overrides


@app.callback()
def configure_logging(verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging.")) -> None:
    """Configure core logging once."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="[%(levelname)s] %(name)s: %(message)s")


@app.command()
def run(  # noqa: D401 - Typer generates help text.
    config: Path = typer.Option(..., exists=True, file_okay=True, dir_okay=False, readable=True, help="Path to YAML config."),
    dry_run: bool = typer.Option(False, help="Generate artifacts without invoking heavy rendering."),
    job_name: Optional[str] = typer.Option(None, "--job-name", "--job.name", help="Override job.name in config."),
    inputs_footage_glob: Optional[str] = typer.Option(
        None,
        "--inputs-footage-glob",
        "--inputs.footage_glob",
        help="Override inputs.footage_glob.",
    ),
    inputs_music_manifest: Optional[str] = typer.Option(
        None,
        "--inputs-music-manifest",
        "--inputs.music_manifest",
        help="Override inputs.music_manifest.",
    ),
    timeline_target_duration: Optional[int] = typer.Option(
        None,
        "--timeline-target-duration",
        "--timeline.target_duration_s",
        min=1,
        help="Override timeline.target_duration_s.",
    ),
    timeline_transition: Optional[str] = typer.Option(
        None,
        "--timeline-transition",
        "--timeline.transition",
        help="Override timeline.transition.",
    ),
    export_resolution: Optional[str] = typer.Option(
        None,
        "--export-resolution",
        "--export.resolution",
        help="Override export.resolution.",
    ),
    export_fps: Optional[int] = typer.Option(
        None,
        "--export-fps",
        "--export.fps",
        min=1,
        help="Override export.fps.",
    ),
) -> None:
    """Run the auto video pipeline for a given config."""
    overrides = _gather_overrides(
        job_name=job_name,
        footage_glob=inputs_footage_glob,
        music_manifest=inputs_music_manifest,
        target_duration=timeline_target_duration,
        transition=timeline_transition,
        export_resolution=export_resolution,
        export_fps=export_fps,
    )
    pipeline_config = build_pipeline_config(config, overrides)
    outputs = run_pipeline(pipeline_config, dry_run=dry_run)
    if outputs:
        for path in outputs:
            console.print(f"[green]Produced: {path}[/green]")
        console.print(f"[green]Pipeline completed. {len(outputs)} video(s) produced.[/green]")
    else:
        console.print("[yellow]Pipeline finished without generating output.[/yellow]")


def main() -> None:
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
