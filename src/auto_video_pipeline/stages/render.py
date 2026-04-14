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
from ..models import MusicPlan, TimelinePlan
from .timeline import CROSSFADE_S

logger = logging.getLogger(__name__)

# macOS system font for Chinese subtitles
MACOS_CHINESE_FONT = "/System/Library/Fonts/STHeiti Light.ttc"


def _subtitle_y(position: str, height: int) -> str:
    """Return ffmpeg Y expression for subtitle vertical position."""
    # Use percentage of height for safe area (avoids edge cutoff)
    if position == "bottom":
        return f"(H*88)/100"  # 88% from top = 12% from bottom
    elif position == "center":
        return "(H-text_h)/2"
    else:  # top
        return "(H*8)/100"


def _build_filter_complex(
    num_clips: int,
    clip_durations: List[float],
    transition: str,
    width: int,
    height: int,
    music: Optional[MusicPlan] = None,
    output_duration: float = 0.0,
    subtitle: Optional[str] = None,
    subtitle_position: str = "bottom",
) -> str:
    """Build the complete ffmpeg filter_complex for video + audio + subtitle."""
    transition = transition.lower()
    cf = CROSSFADE_S if transition in ("crossfade", "dip") else 0.0

    lines: List[str] = []
    fps = 25

    # --- Video: scale + trim each input clip ---
    for i, td in enumerate(clip_durations):
        lines.append(
            f"[{i}:v]trim=0:{td:.3f},setpts=PTS-STARTPTS,fps={fps},"
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},setsar=1[v{i}]"
        )

    # --- Video: concatenate / transition → output label [vout] ---
    if transition in ("crossfade", "dip") and num_clips > 1:
        xfade_type = "fade" if transition == "crossfade" else "dip"
        cumulative = clip_durations[0]
        for i in range(num_clips - 1):
            offset = cumulative - cf
            in1 = f"v{i:02d}" if i > 0 else "v0"
            in2 = f"v{i + 1}"
            out = f"v{i + 1:02d}"
            lines.append(
                f"[{in1}][{in2}]xfade=transition={xfade_type}"
                f":duration={cf}:offset={offset:.3f}[{out}]"
            )
            cumulative += clip_durations[i + 1] - cf
        lines.append(f"[v{num_clips - 1:02d}]null[vout]")
    elif num_clips > 1:
        v_ins = "".join(f"[v{i}]" for i in range(num_clips))
        lines.append(f"{v_ins}concat=n={num_clips}:v=1:a=0[vout]")
    else:
        lines.append("[v0]null[vout]")

    # --- Subtitle overlay on video ---
    if subtitle:
        y_expr = _subtitle_y(subtitle_position, height)
        # Escape single quotes in subtitle text for ffmpeg
        escaped = subtitle.replace("'", "'\\''")
        lines.append(
            f"[vout]drawtext=text='{escaped}':"
            f"fontfile={MACOS_CHINESE_FONT}:"
            f"fontsize={max(width // 20, 40)}:"
            f"fontcolor=white:"
            f"borderw=4:bordercolor=black@0.8:"
            f"x=(w-text_w)/2:"
            f"y={y_expr}:"
            f"[vout_sub]"
        )
        # For clean output reference
        lines.append("[vout_sub]null[vout]")

    # --- Audio ---
    bgm_input_idx = num_clips

    if music and music.file_path.exists():
        fade_in_s = music.fade_in_ms / 1000.0
        fade_out_s = music.fade_out_ms / 1000.0
        fade_out_start = max(output_duration - fade_out_s, fade_in_s)
        lines.append(
            f"[{bgm_input_idx}:a]atrim=0:{output_duration:.3f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d={fade_in_s:.2f},"
            f"afade=t=out:st={fade_out_start:.2f}:d={fade_out_s:.2f},"
            f"volume=0.7[aout]"
        )
    else:
        a_ins = "".join(f"[{i}:a]" for i in range(num_clips))
        lines.append(
            f"{a_ins}amix=inputs={num_clips}:duration=longest"
            f":dropout_transition=0[aout]"
        )

    return ";\n".join(lines)


def _parse_resolution(resolution: str) -> tuple[int, int]:
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

    _write_artifacts(job_dir, config, timeline)

    if timeline.video_total > 1:
        idx = timeline.video_index + 1
        video_path = job_dir / f"draft_{idx:03d}.mp4"
    else:
        video_path = job_dir / "draft.mp4"

    if dry_run:
        video_path.write_text("Dry run - video not rendered.\n", encoding="utf-8")
        logger.info("Dry run complete. Artifacts in %s", job_dir)
        return video_path

    clips = timeline.clips
    if not clips:
        raise ValueError("No clips in timeline to render.")

    transitions = timeline.transitions or ["cut"] * (len(clips) - 1)
    transition = transitions[0] if transitions else "cut"

    clip_durations = [c["end"] - c["start"] for c in clips]
    clip_paths = [c["path"] for c in clips]

    w, h = _parse_resolution(config.export.resolution)

    cf = CROSSFADE_S if transition in ("crossfade", "dip") else 0.0
    output_duration = (
        sum(clip_durations) - (len(clips) - 1) * cf
        if len(clips) > 1 else
        (clip_durations[0] if clip_durations else 0)
    )

    music = timeline.music
    filter_complex = _build_filter_complex(
        num_clips=len(clips),
        clip_durations=clip_durations,
        transition=transition,
        width=w,
        height=h,
        music=music,
        output_duration=output_duration,
        subtitle=timeline.subtitle,
        subtitle_position=timeline.subtitle_position,
    )

    cmd = ["ffmpeg", "-y"]
    for p in clip_paths:
        cmd += ["-i", p]
    if music and music.file_path.exists():
        cmd += ["-i", str(music.file_path)]

    cmd += ["-filter_complex", filter_complex]
    cmd += ["-map", "[vout]", "-map", "[aout]"]
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

    subtitle_info = f", subtitle='{timeline.subtitle}'" if timeline.subtitle else ""
    logger.info(
        "Rendering %d clips (transition=%s, %dx%d%s) -> %s",
        len(clips), transition, w, h, subtitle_info, video_path,
    )

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        _write_diagnostics(
            job_dir, len(clips), transition, timeline.subtitle,
            result.returncode, result.stderr,
        )
        logger.error("ffmpeg failed (code %d):\n%s", result.returncode, result.stderr[-2000:])
        raise RuntimeError(
            f"ffmpeg rendering failed (code {result.returncode}). "
            f"See {job_dir / 'diagnostics.md'}"
        )

    _write_diagnostics(job_dir, len(clips), transition, timeline.subtitle, 0, None)
    logger.info("Render complete: %s", video_path)
    return video_path


def _write_artifacts(
    job_dir: Path,
    config: PipelineConfig,
    timeline: TimelinePlan,
) -> None:
    timeline_data = {
        "duration_s": timeline.duration_s,
        "clips": timeline.clips,
        "transitions": timeline.transitions,
        "music": timeline.music.track_id if timeline.music else None,
        "video_index": timeline.video_index,
        "video_total": timeline.video_total,
        "subtitle": timeline.subtitle,
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
    subtitle: Optional[str],
    returncode: int,
    stderr: Optional[str],
) -> None:
    lines = [
        "# Diagnostics\n",
        f"- clips: {num_clips}",
        f"- transition: {transition}",
        f"- subtitle: {subtitle or '(none)'}",
        f"- ffmpeg_returncode: {returncode}",
    ]
    if stderr:
        lines += ["\n## ffmpeg stderr\n", "```", stderr[-2000:], "```"]
    (job_dir / "diagnostics.md").write_text("\n".join(lines), encoding="utf-8")
