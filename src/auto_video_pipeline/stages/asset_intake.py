"""Asset discovery and normalization."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, List

from ..config import PipelineConfig
from ..models import AssetBundle, ShotMetadata

logger = logging.getLogger(__name__)


def _resolve_paths(footage_glob: str) -> List[Path]:
    matches = sorted(Path().glob(footage_glob))
    return [path for path in matches if path.is_file()]


def _parse_name(path: Path) -> ShotMetadata:
    stem = path.stem
    segments = stem.split("__")
    project = segments[0] if segments else "project"
    scene = segments[1] if len(segments) > 1 else "scene"
    take = segments[2] if len(segments) > 2 else "000"
    tags_segment = segments[3] if len(segments) > 3 else ""
    tags = [tag for tag in tags_segment.replace("-", "_").split("_") if tag]
    return ShotMetadata(
        path=path.resolve(),
        scene=scene,
        take=take,
        tags=tags,
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
