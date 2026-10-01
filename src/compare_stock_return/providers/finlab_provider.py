"""FinLab raw/adjusted contracts remain unchanged."""

from copy import copy
from dataclasses import asdict

from ..asset_id import parse_asset_id
from . import legacy_finlab


class FinLabProvider:
    def load(self, config, asset_ids, cache_root):
        c = copy(config)
        mapping = {parse_asset_id(a).symbol: a for a in asset_ids}
        c.symbols = list(mapping)
        c.custom_assets = {
            parse_asset_id(a).symbol: spec
            for a, spec in config.custom_assets.items()
            if a in asset_ids
        }
        frames, metadata, provenance = legacy_finlab.load(c, cache_root)
        out_meta = {
            a: dict(metadata.get(s, {}), **asdict(parse_asset_id(a)))
            for s, a in mapping.items()
        }
        return {mapping[s]: f for s, f in frames.items()}, out_meta, provenance
