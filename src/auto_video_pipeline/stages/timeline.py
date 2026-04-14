"""Timeline composition utilities."""

from __future__ import annotations

import logging
from typing import List

from ..config import PipelineConfig
from ..models import MusicPlan, ShotMetadata, TimelinePlan

logger = logging.getLogger(__name__)

# Crossfade overlap in seconds — shared with render.py.
CROSSFADE_S = 0.5


def compose_timeline(
    config: PipelineConfig,
    shots: List[ShotMetadata],
    music: MusicPlan | None,
    video_index: int = 0,
    video_total: int = 1,
    subtitle: str | None = None,
    subtitle_position: str = "bottom",
) -> TimelinePlan:
    if not shots:
        raise ValueError("Timeline requires at least one shot.")

    ordered = sorted(
        shots,
        key=lambda shot: (shot.score or 0.0, shot.scene, shot.take),
        reverse=True,
    )

    num_clips = len(ordered)
    transition = config.timeline.transition
    overlap = CROSSFADE_S if transition in ("crossfade", "dip") else 0.0

    # Crossfade-aware slot calculation:
    # total = N * slot - (N-1) * overlap  =>  slot = (target + (N-1)*overlap) / N
    target = config.timeline.target_duration_s
    clip_duration = (target + (num_clips - 1) * overlap) / max(num_clips, 1)
    clip_duration = max(clip_duration, 1.0)

    clips = []
    time_cursor = 0.0
    for shot in ordered:
        actual_out = min(shot.duration_s or clip_duration, clip_duration)
        clip_entry = {
            "path": str(shot.path),
            "in": 0.0,
            "out": actual_out,
            "start": time_cursor,
            "end": time_cursor + clip_duration,
        }
        clips.append(clip_entry)
        time_cursor += clip_duration

    actual_duration = num_clips * clip_duration - (num_clips - 1) * overlap

    transitions = [transition] * (num_clips - 1)
    plan = TimelinePlan(
        job_name=config.job.name,
        duration_s=int(round(actual_duration)),
        clips=clips,
        transitions=transitions,
        music=music,
        video_index=video_index,
        video_total=video_total,
        subtitle=subtitle,
        subtitle_position=subtitle_position,
    )
    logger.info(
        "Timeline %d/%d composed: %d clips, ~%.1fs (transition=%s)",
        video_index + 1, video_total, num_clips, actual_duration, transition,
    )
    return plan
