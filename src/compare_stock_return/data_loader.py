"""Market dispatcher; the explicit legacy entrypoint retains Taiwan defaults."""

from .providers import FinLabProvider, TiingoProvider, legacy_finlab
from .providers.legacy_finlab import AuthenticationError as AuthenticationError
from .providers.legacy_finlab import authenticate as authenticate


def load(config, cache_root) -> tuple[dict, dict, dict]:
    if config.assets is None:
        legacy_finlab.authenticate = authenticate
        return legacy_finlab.load(config, cache_root)
    frames, metadata, provenance = {}, {}, {}
    for market, provider in [("TW", FinLabProvider()), ("US", TiingoProvider())]:
        ids = [a for a in config.assets if a.startswith(market + ":")]
        if ids:
            f, m, p = provider.load(
                config, ids, cache_root / ("finlab" if market == "TW" else "tiingo")
            )
            frames.update(f)
            metadata.update(m)
            provenance[market] = p
    return frames, metadata, provenance
