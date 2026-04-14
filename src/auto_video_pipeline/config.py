"""Configuration loading and override utilities."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError


class JobConfig(BaseModel):
    name: str = "sample_job"
    environment: Literal["local", "cloud"] = "local"


class InputsConfig(BaseModel):
    footage_glob: str = "inputs/raw/**/*.mp4"
    music_manifest: str = "inputs/manifests/music_catalog.yaml"


class TimelineConfig(BaseModel):
    target_duration_s: int = Field(90, ge=1, description="Desired output length in seconds.")
    transition: Literal["cut", "crossfade", "dip"] = "cut"
    clips_per_video: int = Field(0, ge=0, description="Clips per output video. 0 = all in one.")


class ScoringWeightConfig(BaseModel):
    length: float = 0.3
    tag_match: float = 0.5
    motion: float = 0.2


class ScoringConfig(BaseModel):
    min_score: float = Field(0.4, ge=0.0, le=1.0)
    weights: ScoringWeightConfig = ScoringWeightConfig()


class ProfileConfig(BaseModel):
    mandatory_tags: List[str] = Field(default_factory=list)


class MusicDuckingConfig(BaseModel):
    lufs: float = -14.0


class MusicConfig(BaseModel):
    bpm_range: Optional[List[int]] = None
    mood: List[str] = Field(default_factory=list)
    ducking: MusicDuckingConfig = MusicDuckingConfig()


class SubtitleConfig(BaseModel):
    text: str = ""
    position: Literal["top", "center", "bottom"] = "bottom"


class InteractionConfig(BaseModel):
    keywords: List[str] = Field(default_factory=list)


class ExportConfig(BaseModel):
    resolution: str = "1920x1080"
    fps: int = 25
    video_bitrate: Optional[str] = "12M"
    audio_codec: str = "aac"


class PipelineConfig(BaseModel):
    job: JobConfig = JobConfig()
    inputs: InputsConfig = InputsConfig()
    timeline: TimelineConfig = TimelineConfig()
    scoring: ScoringConfig = ScoringConfig()
    profile: ProfileConfig = ProfileConfig()
    music: MusicConfig = MusicConfig()
    subtitles: List[SubtitleConfig] = Field(default_factory=list)
    interaction: InteractionConfig = InteractionConfig()
    export: ExportConfig = ExportConfig()

    def snapshot(self) -> Dict[str, Any]:
        """Return a plain dict suitable for persisting alongside job outputs."""
        return self.model_dump()


def read_config_file(path: Path) -> Dict[str, Any]:
    """Load YAML config from disk."""
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file must define a mapping at root, got {type(data)}")
    return data


def _ensure_branch(data: Dict[str, Any], key: str) -> Dict[str, Any]:
    if key not in data or not isinstance(data[key], dict):
        data[key] = {}
    return data[key]


def apply_override(data: Dict[str, Any], dotted_key: str, value: Any) -> None:
    """Apply a dot-notation override into the config dict."""
    parts = dotted_key.split(".")
    cursor = data
    for part in parts[:-1]:
        cursor = _ensure_branch(cursor, part)
    cursor[parts[-1]] = value


def coerce_value(raw: Any) -> Any:
    """Attempt to interpret override values via YAML semantics."""
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        try:
            loaded = yaml.safe_load(raw)
        except yaml.YAMLError:
            return raw
        return loaded
    return raw


def merge_overrides(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(base)
    for key, value in overrides.items():
        apply_override(merged, key, coerce_value(value))
    return merged


def build_pipeline_config(config_path: Path, overrides: Dict[str, Any]) -> PipelineConfig:
    raw = read_config_file(config_path)
    merged = merge_overrides(raw, overrides)
    try:
        return PipelineConfig.model_validate(merged)
    except ValidationError as exc:  # pragma: no cover - surfaced to CLI
        raise SystemExit(f"Invalid configuration: {exc}") from exc
