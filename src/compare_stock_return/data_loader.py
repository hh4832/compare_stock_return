"""FinLab primary provider and explicit custom total-return NAV input."""

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

DATASETS = {"raw_close": "price:收盤價", "adjusted_close": "etl:adj_close"}


class AuthenticationError(RuntimeError):
    pass


def authenticate() -> None:
    token = os.environ.get("FINLAB_API_TOKEN")
    if not token:
        try:
            from google.colab import userdata

            token = userdata.get("FINLAB_API_TOKEN")
        except ImportError:
            pass
        except Exception:
            raise AuthenticationError(
                "Cannot access Colab Secret FINLAB_API_TOKEN"
            ) from None
    if not token:
        raise AuthenticationError(
            "Set FINLAB_API_TOKEN via environment or Colab Secrets"
        )
    import finlab

    finlab.login(token)


def load(config, cache_root: Path) -> tuple[dict, dict, dict]:
    assets, metadata, provenance = {}, {}, {}
    symbols = [s for s in config.symbols if s not in config.custom_assets]
    if symbols:
        authenticate()
        from finlab import data

        cache_root.mkdir(parents=True, exist_ok=True)
        tables = {}
        for column, dataset in DATASETS.items():
            key = hashlib.sha256(
                (dataset + "|" + ",".join(sorted(symbols))).encode()
            ).hexdigest()[:20]
            path = cache_root / f"{key}.parquet"
            meta_path = cache_root / f"{key}.json"
            cached = False
            if (
                config.use_cache
                and not config.refresh_cache
                and path.exists()
                and meta_path.exists()
            ):
                info = json.loads(meta_path.read_text())
                age = (
                    datetime.now(timezone.utc)
                    - datetime.fromisoformat(info["downloaded_at"])
                ).total_seconds() / 3600
                cached = (
                    0 <= age <= config.cache_max_age_hours
                    and info.get("dataset") == dataset
                    and info.get("symbols") == sorted(symbols)
                )
            if cached:
                table = pd.read_parquet(path)
            else:
                # Reject absent columns before any selection; preserve market calendar rows.
                table = pd.DataFrame(data.get(dataset, force_download=True))
                absent = set(symbols) - set(table.columns)
                if absent:
                    raise ValueError(f"{dataset}: missing tickers {sorted(absent)}")
                table = table[symbols]
                info = dict(
                    dataset=dataset,
                    symbols=sorted(symbols),
                    downloaded_at=datetime.now(timezone.utc).isoformat(),
                )
                if config.use_cache:
                    table.to_parquet(path)
                    meta_path.write_text(json.dumps(info, indent=2))
            table.index = pd.to_datetime(table.index)
            # Never include future calendar rows in live comparisons.
            table = table.loc[
                table.index.normalize()
                <= pd.Timestamp.now(tz="Asia/Taipei").tz_localize(None).normalize()
            ]
            tables[column] = table
            provenance[column] = dict(
                **info, cache_hit=cached, last_dataset_date=str(table.index.max())
            )
        for s in symbols:
            assets[s] = pd.concat({c: t[s] for c, t in tables.items()}, axis=1)
        try:
            categories = pd.DataFrame(data.get("security_categories")).reset_index()
            id_column = "symbol" if "symbol" in categories else "stock_id"
            if {id_column, "name", "market"} <= set(categories):
                for _, row in categories.iterrows():
                    market = str(row["market"])
                    asset_type = {
                        "etf": "ETF",
                        "sii": "listed stock",
                        "otc": "OTC stock",
                    }.get(market, f"provider market: {market}")
                    metadata[str(row[id_column])] = {
                        "name": row["name"],
                        "type": asset_type,
                    }
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "Optional company metadata unavailable: %s", type(exc).__name__
            )
    for s, spec in config.custom_assets.items():
        if s not in config.symbols:
            continue
        if not spec.get("total_return_confirmed"):
            raise ValueError(
                f"{s}: custom adjusted NAV needs total_return_confirmed=true"
            )
        f = pd.read_csv(spec["path"], parse_dates=["date"]).set_index("date")
        assets[s] = f[["raw_close", "adjusted_close"]]
        metadata[s] = dict(name=spec.get("name", s), type="custom NAV")
        provenance[s] = dict(
            source=spec.get("source", "user supplied"),
            sha256=hashlib.sha256(Path(spec["path"]).read_bytes()).hexdigest(),
        )
    return assets, metadata, provenance
