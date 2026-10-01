"""Small EOD client. Credentials only in Authorization, never cache or error payloads."""

import hashlib
import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from urllib.parse import quote

import numpy as np
import pandas as pd
import requests

from ..asset_id import parse_asset_id
from ..validation import DataQualityError, validate_assets


class AuthenticationError(RuntimeError):
    pass


def token_from_environment() -> str:
    token = os.environ.get("TIINGO_API_TOKEN")
    if not token:
        try:
            from google.colab import userdata

            token = userdata.get("TIINGO_API_TOKEN")
        except ImportError:
            pass
        except Exception:
            raise AuthenticationError(
                "Cannot access Colab Secret TIINGO_API_TOKEN"
            ) from None
    if not token:
        raise AuthenticationError(
            "Set TIINGO_API_TOKEN via environment or Colab Secrets"
        )
    return token


def normalize(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if not {"date", "close", "adjClose", "divCash", "splitFactor"} <= set(frame):
        raise ValueError("Tiingo response lacks required EOD fields")
    frame.index = (
        pd.to_datetime(frame.pop("date"), utc=True).dt.tz_localize(None).dt.normalize()
    )
    frame.index.name = "date"
    # Do not sort away malformed source order or collapse duplicate sessions.
    frame = frame[["close", "adjClose", "divCash", "splitFactor"]].apply(
        pd.to_numeric, errors="raise"
    )
    frame["raw_close"] = frame.close
    frame["adjusted_close"] = frame.adjClose
    if frame[["raw_close", "adjusted_close"]].isna().any().any():
        raise DataQualityError(
            pd.DataFrame(
                [
                    dict(
                        ticker="US:provider",
                        policy="Tiingo returned a session without both prices",
                    )
                ]
            )
        )
    validate_assets({"US:provider": frame})
    if (
        not np.isfinite(frame[["divCash", "splitFactor"]]).all().all()
        or (frame.divCash < 0).any()
        or (frame.splitFactor <= 0).any()
    ):
        raise ValueError("Invalid Tiingo corporate-action audit fields")
    return frame


class TiingoProvider:
    def __init__(self, session=None):
        self.session = session or requests.Session()

    def load(self, config, asset_ids, cache_root):
        cache_root.mkdir(parents=True, exist_ok=True)
        frames, metadata, provenance = {}, {}, {}
        for asset in asset_ids:
            identity = parse_asset_id(asset)
            # Full history allows pairwise analyses longer than a custom headline window.
            end = str(pd.Timestamp.now(tz="America/New_York").date())
            request = dict(
                provider="tiingo",
                ticker=identity.symbol,
                endpoint="daily/prices",
                startDate="1900-01-01",
                endDate=end,
            )
            key = hashlib.sha256(
                json.dumps(request, sort_keys=True).encode()
            ).hexdigest()[:24]
            path, meta_path = (
                cache_root / (key + ".parquet"),
                cache_root / (key + ".json"),
            )
            hit = False
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
                hit = (
                    0 <= age <= config.cache_max_age_hours
                    and info.get("request") == request
                )
            if hit:
                frame = pd.read_parquet(path)
                frame = normalize(frame.reset_index().to_dict("records"))
            else:
                token = token_from_environment()
                try:
                    response = self.session.get(
                        "https://api.tiingo.com/tiingo/daily/"
                        + quote(identity.symbol, safe="")
                        + "/prices",
                        params={
                            "startDate": request["startDate"],
                            "endDate": end,
                            "format": "json",
                        },
                        headers={"Authorization": "Token " + token},
                        timeout=30,
                    )
                    response.raise_for_status()
                    rows = response.json()
                except Exception:
                    raise RuntimeError(
                        "Tiingo EOD request failed; provider payload omitted"
                    ) from None
                finally:
                    token = None
                frame = normalize(rows)
                info = dict(
                    request=request,
                    provider="tiingo",
                    downloaded_at=datetime.now(timezone.utc).isoformat(),
                )
                if config.use_cache:
                    frame.to_parquet(path)
                    meta_path.write_text(json.dumps(info, indent=2))
            if (frame.index > pd.Timestamp(end)).any():
                raise ValueError("Tiingo returned dates beyond requested range")
            frames[asset] = frame
            metadata[asset] = asdict(identity)
            provenance[asset] = dict(
                **info,
                cache_hit=hit,
                first_date=str(frame.index.min().date()),
                last_date=str(frame.index.max().date()),
                last_dataset_date=str(frame.index.max().date()),
                rows=len(frame),
                calendar_policy="provider-returned sessions; absent session rows not independently verified",
            )
        return frames, metadata, provenance
