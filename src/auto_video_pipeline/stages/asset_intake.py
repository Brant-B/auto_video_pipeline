"""Asset discovery and normalization."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import List, Optional

from ..config import PipelineConfig
from ..models import AssetBundle, ShotMetadata

logger = logging.getLogger(__name__)


def _resolve_paths(footage_glob: str) -> List[Path]:
    matches = sorted(Path().glob(footage_glob))
    return [path for path in matches if path.is_file()]


def _get_duration(path: Path) -> Optional[float]:
    """Query ffprobe for the video duration in seconds."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "format=duration",
                "-of", "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return float(data["format"]["duration"])
    except Exception as exc:
        logger.warning("Could not get duration for %s: %s", path.name, exc)
    return None


def _parse_name(path: Path) -> ShotMetadata:
    """Parse filename. Supports both __ convention and plain Chinese filenames."""
    stem = path.stem
    segments = stem.split("__")

    if len(segments) >= 2:
        # 标准格式: 项目__场景__镜次__标签
        scene = segments[1] if len(segments) > 1 else "scene"
        take = segments[2] if len(segments) > 2 else "000"
        tags_segment = segments[3] if len(segments) > 3 else ""
        tags = [tag for tag in tags_segment.replace("-", "_").split("_") if tag]
    else:
        # 中文文件名或无分隔符格式：直接用原文件名作为场景名
        scene = stem
        take = "001"
        tags = []

    duration_s = _get_duration(path)
    return ShotMetadata(
        path=path.resolve(),
        scene=scene,
        take=take,
        tags=tags,
        duration_s=duration_s,
        reasons=[f"parsed_from:{stem}"],
    )


def collect_assets(config: PipelineConfig) -> AssetBundle:
    """Scan the input glob and convert filenames into structured metadata."""
    paths = _resolve_paths(config.inputs.footage_glob)
    if not paths:
        logger.warning("No footage matched glob %s", config.inputs.footage_glob)
    shots = [_parse_name(path) for path in paths]
    project = shots[0].path.stem.split("__")[0] if shots else config.job.name
    logger.info("Collected %d shots for project %s", len(shots), project)
    return AssetBundle(project=project, shots=shots)
