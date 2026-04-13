# Pipeline Specification

_Covers input conventions, stage contracts, configuration schema, and expected outputs for the v0.1 MVP._

## 1. Directory & Naming Conventions

```
auto_video_pipeline/
├─ inputs/
│  ├─ raw/<project>/<timestamp>__<scene>__<take>__<tag>.mp4
│  ├─ music/<bpm>_<mood>_<id>.wav
│  └─ manifests/music_catalog.yaml
├─ configs/
│  └─ sample_job.yaml
└─ outputs/<project>/<job_id>/
   ├─ draft.mp4
   ├─ timeline.json
   ├─ config.snapshot.yaml
   └─ diagnostics.md
```

### Footage Naming

`<project>__<scene>__<take>__<tag>.mp4`

- `project`: slug (snake_case) shared by every clip in the batch.
- `scene`: alphanumeric identifier, e.g., `S01A`.
- `take`: incremental numeric or timestamp.
- `tag`: underscore-delimited descriptors (`close`, `drone`, `NG`, `hero`).

### Music Naming

`<bpm>_<mood>_<id>.wav`

- `bpm`: integer tempo, used for filtering.
- `mood`: one or more tokens separated by `-` (`uplift`, `cinematic`, `dark`).
- `id`: unique short id referencing catalog metadata.

## 2. Stage Contracts

| Stage | Input | Output | Notes |
| --- | --- | --- | --- |
| `intake.validate_assets` | Config + footage/music globs | `assets.json` (normalized metadata) | Hard fail on missing footage/music. |
| `scoring.rank_shots` | `assets.json`, config scoring block | `timeline_shots.json` | Adds `score`, `reason`, `in/out`. |
| `music.pick_track` | Music manifest, timeline duration | `music_plan.json` | Contains track id, start offset, fade timings. |
| `timeline.compose` | Shots + music plan | `timeline.json` | EDL-style structure consumed by renderer. |
| `render.export` | Timeline JSON, export config | `draft.mp4`, preview GIF, logs | All artifacts stored under job output. |

Each stage writes to `outputs/<project>/<job_id>/artifacts/<stage>.json` to aid debugging.

## 3. Configuration Schema (YAML)

| Key | Type | Required | Description |
| --- | --- | --- | --- |
| `job.name` | string | yes | Unique identifier per run. |
| `job.environment` | enum(`local`,`cloud`) | no | Controls path resolver + logging verbosity. |
| `inputs.footage_glob` | string | yes | Glob for footage; can include project placeholder. |
| `inputs.music_manifest` | path | yes | Points to YAML/CSV describing music catalog. |
| `timeline.target_duration_s` | int | yes | Desired duration; used to trim/extend timeline. |
| `timeline.transition` | enum(`cut`,`crossfade`,`dip`) | no | Transition type between shots. |
| `scoring.weights.length` | float | yes | Weight for length adherence. |
| `scoring.weights.tag_match` | float | yes | Weight for tag alignment with `project_profile`. |
| `scoring.weights.motion` | float | no | Weight for optical flow or variance heuristics. |
| `scoring.min_score` | float 0-1 | no | Filter threshold; below -> drop clip. |
| `profile.mandatory_tags` | list | no | Tags that must appear at least once in final timeline. |
| `music.bpm_range` | [int,int] | no | Acceptable BPM interval. |
| `music.mood` | list | no | Acceptable moods; defaults to project profile. |
| `music.ducking.lufs` | float | no | Target loudness (default -14). |
| `export.resolution` | string WxH | yes | Example `1920x1080`. |
| `export.fps` | int | yes | Output frame rate. |
| `export.video_bitrate` | string | no | ffmpeg-friendly bitrate expression. |
| `export.audio_codec` | string | no | Default `aac`. |

### Sample Job

```yaml
job:
  name: trail_launch_v001
  environment: local
inputs:
  footage_glob: "inputs/raw/trail_launch/*.mp4"
  music_manifest: "inputs/manifests/music_catalog.yaml"
timeline:
  target_duration_s: 75
  transition: crossfade
scoring:
  min_score: 0.45
  weights:
    length: 0.35
    tag_match: 0.45
    motion: 0.2
profile:
  mandatory_tags: ["hero", "product"]
music:
  bpm_range: [95, 110]
  mood: ["uplifting", "energetic"]
  ducking:
    lufs: -14
export:
  resolution: "1920x1080"
  fps: 25
  video_bitrate: "12M"
  audio_codec: "aac"
```

## 4. Shot Scoring Heuristics (v0.1)

1. **Length fit**: penalize shots shorter than 1.2 seconds or longer than 6 seconds.
2. **Tag match**: boost if tags overlap with `profile.mandatory_tags`.
3. **Take quality**: if filename includes `_NG` or `_bad`, set score to 0.
4. **Motion heuristic**: optional; use ffmpeg `select=gt(scene,0.4)` count or optical flow variance.
5. **Diversity**: ensure at least one clip per `scene` by re-inserting if coverage missing.

Scoring function example:

```
score = w_length * length_score
      + w_tag * tag_overlap
      + w_motion * motion_metric
```

Normalize to 0-1. Anything below `scoring.min_score` is discarded.

## 5. Music Planning

- Catalog manifest fields: `id`, `bpm`, `mood`, `duration`, `key`, `file`.
- Selection priority: (1) mood match count, (2) BPM closeness, (3) minimal trimming.
- Envelope: 400 ms fade in/out, apply ducking around dialogue tags when available.
- Support optional secondary track for intro/outro in later milestones.

## 6. CLI Contract (planned)

```
python -m auto_video_pipeline.run --config configs/sample_job.yaml --dry-run
```

Flags:

- `--dry-run`: run until timeline generation, skip render.
- `--resume <job_id>`: reuse cached metadata to continue failed render.
- `--profile <name>`: override config with entries from `configs/profiles/<name>.yaml`.

## 7. Outputs

| File | Description |
| --- | --- |
| `draft.mp4` | Final render. |
| `timeline.json` | Machine-readable timeline for audits. |
| `config.snapshot.yaml` | Frozen config used for the run. |
| `artifacts/<stage>.json` | Intermediate data per stage. |
| `diagnostics.md` | Human-readable summary, errors, and TODOs. |
| `preview.gif` (optional) | Short GIF for quick review. |

## 8. Validation Checklist

- ✅ Inputs exist and match glob.
- ✅ Unique tags coverage satisfied.
- ✅ Timeline duration within ±5 seconds of target.
- ✅ Audio LUFS within ±1 dB of target.
- ✅ Export succeeded without ffmpeg error code.

Automation idea: add `python -m auto_video_pipeline.check outputs/<project>/<job_id>` to assert these conditions in CI later.
