"""Rendering/export stage using ffmpeg."""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import yaml

from ..config import ExportConfig, PipelineConfig
from ..models import TimelinePlan

logger = logging.getLogger(__name__)

CROSSFADE_S = 0.5  # seconds of overlap between clips


def _build_filter_complex(
    num_clips: int,
    clip_durations: List[float],
    transition: str,
    width: int,
    height: int,
) -> str:
    """Build the complete ffmpeg filter_complex for video + audio."""
    transition = transition.lower()
    cf = CROSSFADE_S if transition in ("crossfade", "dip") else 0.0
    trim_d = [d - cf for d in clip_durations]

    lines: List[str] = []
    fps = 25  # fixed output fps for constant frame rate

    # --- Video: scale + trim each input clip ---
    for i, td in enumerate(trim_d):
        lines.append(
            f"[{i}:v]trim=0:{td:.3f},setpts=PTS-STARTPTS,fps={fps},"
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1[v{i}]"
        )

    # --- Video: concatenate / transition ---
    if transition in ("crossfade", "dip") and num_clips > 1:
        xfade_type = "fade" if transition == "crossfade" else "dip"
        # For chained xfade, offset = cumulative output duration - cf.
        # After each xfade, cumulative += trim_d[next] - cf.
        cumulative = trim_d[0]
        for i in range(num_clips - 1):
            offset = cumulative - cf
            in1 = f"v{i:02d}" if i > 0 else "v0"
            in2 = f"v{i + 1}"
            out = f"v{i + 1:02d}"
            lines.append(
                f"[{in1}][{in2}]xfade=transition={xfade_type}"
                f":duration={cf}:offset={offset:.3f}[{out}]"
            )
            cumulative += trim_d[i + 1] - cf
        lines.append(f"[v{num_clips - 1:02d}]null[out]")
    elif num_clips > 1:
        # cut mode: simple concat
        v_ins = "".join(f"[v{i}]" for i in range(num_clips))
        lines.append(f"{v_ins}concat=n={num_clips}:v=1:a=0[out]")
    else:
        lines.append("[v0]null[out]")

    # --- Audio: mix all clip audio streams ---
    a_ins = "".join(f"[{i}:a]" for i in range(num_clips))
    lines.append(
        f"{a_ins}amix=inputs={num_clips}:duration=longest:dropout_transition=0[aout]"
    )

    return ";\n".join(lines)


def _parse_resolution(resolution: str) -> tuple[int, int]:
    """Parse '1920x1080' into (1920, 1080)."""
    parts = resolution.lower().split("x")
    return int(parts[0]), int(parts[1])


def export_draft(
    config: PipelineConfig,
    timeline: TimelinePlan,
    dry_run: bool = False,
) -> Path:
    """Render the timeline to a real MP4 using ffmpeg."""
    output_dir = Path("outputs") / config.job.name
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    job_dir = output_dir / f"run-{timestamp}"
    job_dir.mkdir(parents=True, exist_ok=True)

    # --- Always persist metadata artifacts ---
    _write_artifacts(job_dir, config, timeline)

    video_path = job_dir / "draft.mp4"

    if dry_run:
        video_path.write_text("Dry run - video not rendered.\n", encoding="utf-8")
        logger.info("Dry run complete. Artifacts in %s", job_dir)
        return video_path

    # --- Build and run ffmpeg ---
    clips = timeline.clips
    if not clips:
        raise ValueError("No clips in timeline to render.")

    transitions = timeline.transitions or ["cut"] * (len(clips) - 1)
    transition = transitions[0] if transitions else "cut"

    clip_durations = [c["end"] - c["start"] for c in clips]
    clip_paths = [c["path"] for c in clips]

    w, h = _parse_resolution(config.export.resolution)
    filter_complex = _build_filter_complex(
        num_clips=len(clips),
        clip_durations=clip_durations,
        transition=transition,
        width=w,
        height=h,
    )

    # ffmpeg command
    cmd = ["ffmpeg", "-y"]
    for p in clip_paths:
        cmd += ["-i", p]
    cmd += ["-filter_complex", filter_complex]
    cmd += ["-map", "[out]", "-map", "[aout]"]
    cmd += [
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-r", str(config.export.fps),
    ]
    if config.export.video_bitrate:
        cmd += ["-b:v", config.export.video_bitrate]
    cmd += [
        "-c:a", config.export.audio_codec,
        "-movflags", "+faststart",
        str(video_path),
    ]

    logger.info(
        "Rendering %d clips (transition=%s, %dx%d) -> %s",
        len(clips), transition, w, h, video_path,
    )
    logger.debug("ffmpeg filter_complex:\n%s", filter_complex)

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        _write_diagnostics(job_dir, len(clips), transition, result.returncode, result.stderr)
        logger.error("ffmpeg failed (code %d):\n%s", result.returncode, result.stderr[-2000:])
        raise RuntimeError(
            f"ffmpeg rendering failed (code {result.returncode}). "
            f"See {job_dir / 'diagnostics.md'}"
        )

    _write_diagnostics(job_dir, len(clips), transition, 0, None)
    logger.info("Render complete: %s", video_path)
    return video_path


def _write_artifacts(
    job_dir: Path,
    config: PipelineConfig,
    timeline: TimelinePlan,
) -> None:
    """Write timeline.json and config.snapshot.yaml."""
    timeline_data = {
        "duration_s": timeline.duration_s,
        "clips": timeline.clips,
        "transitions": timeline.transitions,
        "music": timeline.music.track_id if timeline.music else None,
    }
    (job_dir / "timeline.json").write_text(
        json.dumps(timeline_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (job_dir / "config.snapshot.yaml").write_text(
        yaml.safe_dump(config.snapshot(), sort_keys=False), encoding="utf-8"
    )


def _write_diagnostics(
    job_dir: Path,
    num_clips: int,
    transition: str,
    returncode: int,
    stderr: Optional[str],
) -> None:
    """Write diagnostics.md with render results."""
    lines = [
        "# Diagnostics\n",
        f"- clips: {num_clips}",
        f"- transition: {transition}",
        f"- ffmpeg_returncode: {returncode}",
    ]
    if stderr:
        lines += ["\n## ffmpeg stderr\n", "```", stderr[-2000:], "```"]
    (job_dir / "diagnostics.md").write_text("\n".join(lines), encoding="utf-8")
