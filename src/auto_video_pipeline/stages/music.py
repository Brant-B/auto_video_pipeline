"""Music selection stage."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from ..config import PipelineConfig
from ..models import MusicPlan

logger = logging.getLogger(__name__)


def _load_manifest(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        logger.warning("Music manifest not found: %s", path)
        return []
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or []
    if isinstance(data, list):
        return data
    logger.error("Music manifest must be a list of tracks, got %s", type(data))
    return []


def _match_track(
    tracks: List[Dict[str, Any]],
    bpm_range: Optional[List[int]],
    desired_moods: List[str],
) -> Optional[Dict[str, Any]]:
    desired = {m.lower() for m in desired_moods}
    candidates: List[Dict[str, Any]] = []
    for track in tracks:
        bpm = track.get("bpm")
        mood_values = {m.lower() for m in track.get("mood", [])}
        if bpm_range and bpm is not None:
            if bpm < bpm_range[0] or bpm > bpm_range[1]:
                continue
        if desired and not (mood_values & desired):
            continue
        candidates.append(track)
    if candidates:
        return candidates[0]
    return tracks[0] if tracks else None


def plan_music(config: PipelineConfig, timeline_duration_s: int) -> Optional[MusicPlan]:
    tracks = _load_manifest(Path(config.inputs.music_manifest))
    if not tracks:
        return None
    track = _match_track(tracks, config.music.bpm_range, config.music.mood)
    if not track:
        logger.warning("No music track satisfied filters, skipping music stage.")
        return None

    plan = MusicPlan(
        track_id=str(track.get("id", "track")),
        file_path=Path(track["file"]).resolve() if track.get("file") else Path(),
        bpm=track.get("bpm"),
        mood=track.get("mood", []),
        fade_in_ms=400,
        fade_out_ms=400,
        duration_s=track.get("duration"),
    )
    logger.info(
        "Selected track %s (bpm=%s mood=%s) for target duration %ss",
        plan.track_id,
        plan.bpm,
        plan.mood,
        timeline_duration_s,
    )
    return plan
