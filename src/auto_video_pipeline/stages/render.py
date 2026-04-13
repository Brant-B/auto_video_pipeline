"""Rendering/export stage (placeholder implementation)."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import yaml

from ..config import PipelineConfig
from ..models import TimelinePlan

logger = logging.getLogger(__name__)


def export_draft(config: PipelineConfig, timeline: TimelinePlan, dry_run: bool = False) -> Path:
    """Persist timeline artifacts and (optionally) a placeholder video file."""
    output_dir = Path("outputs") / config.job.name
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    job_dir = output_dir / f"run-{timestamp}"
    job_dir.mkdir(parents=True, exist_ok=True)

    timeline_path = job_dir / "timeline.json"
    config_snapshot_path = job_dir / "config.snapshot.yaml"
    diagnostics_path = job_dir / "diagnostics.md"
    video_path = job_dir / "draft.mp4"

    timeline_dict = {
        "duration_s": timeline.duration_s,
        "clips": timeline.clips,
        "transitions": timeline.transitions,
        "music": timeline.music.track_id if timeline.music else None,
    }
    timeline_path.write_text(json.dumps(timeline_dict, indent=2), encoding="utf-8")
    config_snapshot_path.write_text(
        yaml.safe_dump(config.snapshot(), sort_keys=False),
        encoding="utf-8",
    )

    diagnostics_path.write_text(
        f"# Diagnostics\n\n- clips: {len(timeline.clips)}\n- dry_run: {dry_run}\n",
        encoding="utf-8",
    )

    if dry_run:
        video_path.write_text("Dry run - video not rendered.\n", encoding="utf-8")
    else:
        video_path.write_text(
            "Placeholder render. Replace with ffmpeg/moviepy implementation.\n",
            encoding="utf-8",
        )
    logger.info("Artifacts written to %s", job_dir)
    return video_path
