"""Top-level orchestration for the auto video pipeline."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from .config import PipelineConfig
from .stages import asset_intake, music, render, scoring, timeline

logger = logging.getLogger(__name__)


def run_pipeline(config: PipelineConfig, dry_run: bool = False) -> Optional[Path]:
    """Execute the pipeline according to the provided configuration."""
    logger.info("Starting job %s (dry_run=%s)", config.job.name, dry_run)
    assets = asset_intake.collect_assets(config)
    scored_shots = scoring.rank_shots(config, assets.shots)
    if not scored_shots:
        logger.warning("No shots remained after scoring; aborting run.")
        return None
    music_plan = music.plan_music(config, config.timeline.target_duration_s)
    timeline_plan = timeline.compose_timeline(config, scored_shots, music_plan)
    output_path = render.export_draft(config, timeline_plan, dry_run=dry_run)
    logger.info("Job %s complete. Output: %s", config.job.name, output_path)
    return output_path
