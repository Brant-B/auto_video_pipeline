"""Shared dataclasses used by pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass(slots=True)
class ShotMetadata:
    path: Path
    scene: str
    take: str
    tags: List[str] = field(default_factory=list)
    duration_s: Optional[float] = None
    score: Optional[float] = None
    reasons: List[str] = field(default_factory=list)


@dataclass(slots=True)
class AssetBundle:
    project: str
    shots: List[ShotMetadata]


@dataclass(slots=True)
class MusicPlan:
    track_id: str
    file_path: Path
    bpm: Optional[int] = None
    mood: List[str] = field(default_factory=list)
    start_offset_s: float = 0.0
    fade_in_ms: int = 400
    fade_out_ms: int = 400
    duration_s: Optional[float] = None


@dataclass(slots=True)
class TimelinePlan:
    job_name: str
    duration_s: int
    clips: List[Dict[str, float]] = field(default_factory=list)
    transitions: List[str] = field(default_factory=list)
    music: Optional[MusicPlan] = None
    video_index: int = 0
    video_total: int = 1
