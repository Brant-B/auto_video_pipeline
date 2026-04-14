"""Top-level orchestration for the auto video pipeline."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from .config import PipelineConfig
from .stages import asset_intake, music, render, scoring, timeline

logger = logging.getLogger(__name__)


def _partition_shots(
    shots: List, clips_per_video: int
) -> List[List]:
    """Split shots into evenly-sized groups. Avoids tiny leftover groups."""
    n = len(shots)
    if n <= clips_per_video or clips_per_video <= 0:
        return [shots]

    num_groups = -(-n // clips_per_video)  # ceiling division
    base = n // num_groups
    extra = n % num_groups

    groups = []
    idx = 0
    for g in range(num_groups):
        size = base + (1 if g < extra else 0)
        groups.append(shots[idx : idx + size])
        idx += size
    return groups


def run_pipeline(
    config: PipelineConfig, dry_run: bool = False
) -> List[Path]:
    """Execute the pipeline, producing one or more output videos."""
    logger.info("Starting job %s (dry_run=%s)", config.job.name, dry_run)

    assets = asset_intake.collect_assets(config)
    scored_shots = scoring.rank_shots(config, assets.shots)
    if not scored_shots:
        logger.warning("No shots remained after scoring; aborting run.")
        return []

    # Partition shots into groups
    cpv = config.timeline.clips_per_video
    if cpv > 0:
        groups = _partition_shots(scored_shots, cpv)
    else:
        groups = [scored_shots]

    video_total = len(groups)
    logger.info("Producing %d video(s) from %d clips", video_total, len(scored_shots))

    outputs: List[Path] = []
    for idx, group in enumerate(groups):
        group_duration = config.timeline.target_duration_s
        music_plan = music.plan_music(config, group_duration)

        timeline_plan = timeline.compose_timeline(
            config, group, music_plan,
            video_index=idx,
            video_total=video_total,
        )

        output_path = render.export_draft(config, timeline_plan, dry_run=dry_run)
        if output_path:
            outputs.append(output_path)
        logger.info(
            "Video %d/%d complete: %s", idx + 1, video_total, output_path
        )

    logger.info("Job %s complete. %d video(s) produced.", config.job.name, len(outputs))
    return outputs
