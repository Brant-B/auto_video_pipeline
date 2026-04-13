"""Simple scoring heuristics for MVP."""

from __future__ import annotations

import logging
from typing import List, Set

from ..config import PipelineConfig
from ..models import ShotMetadata

logger = logging.getLogger(__name__)

LOW_QUALITY_TAGS = {"ng", "bad"}


def _tag_overlap_score(tags: Set[str], mandatory: Set[str]) -> float:
    if not mandatory:
        return 0.5 if tags else 0.0
    overlap = tags & mandatory
    return len(overlap) / len(mandatory)


def _length_score(shot: ShotMetadata) -> float:
    if shot.duration_s is None:
        return 0.7
    if shot.duration_s < 1.2:
        return 0.2
    if shot.duration_s > 6.0:
        return 0.4
    return 1.0


def rank_shots(config: PipelineConfig, shots: List[ShotMetadata]) -> List[ShotMetadata]:
    """Assign heuristic scores and drop clips below the configured threshold."""
    keep: List[ShotMetadata] = []
    mandatory = {tag.lower() for tag in config.profile.mandatory_tags}
    weights = config.scoring.weights

    for shot in shots:
        tags = {tag.lower() for tag in shot.tags}
        if tags & LOW_QUALITY_TAGS:
            shot.score = 0.0
            shot.reasons.append("filtered:low_quality_tag")
            logger.debug("Dropping %s due to low quality tag", shot.path.name)
            continue

        length_component = _length_score(shot)
        tag_component = _tag_overlap_score(tags, mandatory)
        motion_component = 0.5  # Placeholder until motion metrics exist.

        score = (
            weights.length * length_component
            + weights.tag_match * tag_component
            + weights.motion * motion_component
        )
        shot.score = round(score, 3)
        shot.reasons.append(f"score:{shot.score}")

        if shot.score < config.scoring.min_score:
            logger.debug("Dropping %s due to score %.2f", shot.path.name, shot.score)
            continue
        keep.append(shot)

    logger.info("Scoring kept %d/%d shots", len(keep), len(shots))
    return keep
