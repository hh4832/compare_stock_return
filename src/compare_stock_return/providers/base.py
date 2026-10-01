"""Normalized providers return asset frames, metadata and provenance."""

from pathlib import Path
from typing import Protocol


class Provider(Protocol):
    def load(
        self, config, asset_ids: list[str], cache_root: Path
    ) -> tuple[dict, dict, dict]: ...
