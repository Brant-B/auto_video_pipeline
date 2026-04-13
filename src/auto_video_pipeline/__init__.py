"""Core package for auto_video_pipeline."""

from importlib import metadata

try:
    __version__ = metadata.version("auto_video_pipeline")
except metadata.PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"

from .pipeline import run_pipeline  # noqa: F401
