"""Timeline composition utilities."""

from __future__ import annotations

import logging
from typing import List

from ..config import PipelineConfig
from ..models import MusicPlan, ShotMetadata, TimelinePlan

logger = logging.getLogger(__name__)


def compose_timeline(
    config: PipelineConfig,
    shots: List[ShotMetadata],
    music: MusicPlan | None,
) -> TimelinePlan:
    if not shots:
        raise ValueError("Timeline requires at least one shot.")

    ordered = sorted(
        shots,
        key=lambda shot: (shot.score or 0.0, shot.scene, shot.take),
        reverse=True,
    )
    target_duration = config.timeline.target_duration_s
    clip_duration = max(target_duration / max(len(ordered), 1), 1.0)

    clips = []
    time_cursor = 0.0
    for shot in ordered:
        clip_entry = {
            "path": str(shot.path),
            "in": 0.0,
            "out": min(shot.duration_s or clip_duration, clip_duration),
            "start": time_cursor,
            "end": time_cursor + clip_duration,
        }
        clips.append(clip_entry)
        time_cursor += clip_duration

    transitions = [config.timeline.transition] * (len(clips) - 1)
    plan = TimelinePlan(
        job_name=config.job.name,
        duration_s=target_duration,
        clips=clips,
        transitions=transitions,
        music=music,
    )
    logger.info(
        "Timeline composed with %d clips (target duration %ss)",
        len(clips),
        target_duration,
    )
    return plan
