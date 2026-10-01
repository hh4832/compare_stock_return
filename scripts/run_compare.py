"""CLI entry point to the same pipeline as Colab."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compare_stock_return.config import Config
from compare_stock_return.pipeline import run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/default.yaml")
    parser.add_argument(
        "--symbols", nargs="+", help="Explicit legacy Taiwan-only layer"
    )
    parser.add_argument("--assets", nargs="+")
    parser.add_argument("--fx-mode", default="none")
    parser.add_argument("--missing-data-policy", choices=["error", "warn", "ignore"])
    parser.add_argument("--benchmark")
    parser.add_argument(
        "--date-mode", choices=["intersection", "full_history", "custom"]
    )
    parser.add_argument("--return-type", choices=["total_return", "price_return"])
    parser.add_argument("--output-root")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--refresh-cache", action="store_true")
    args = parser.parse_args()
    config = Config.from_yaml(args.config)
    for arg, field in [
        ("symbols", "symbols"),
        ("assets", "assets"),
        ("fx_mode", "fx_mode"),
        ("missing_data_policy", "missing_data_policy"),
        ("benchmark", "benchmark"),
        ("date_mode", "date_mode"),
        ("return_type", "return_type"),
        ("output_root", "drive_output_root"),
        ("start", "custom_start_date"),
        ("end", "custom_end_date"),
    ]:
        value = getattr(args, arg)
        if value is not None:
            setattr(config, field, value)
    if args.symbols:
        if args.assets:
            parser.error("Use either assets or legacy symbols")
        config.assets = None
        config.portfolios = {}
        config.benchmark = args.benchmark or args.symbols[0]
    if args.assets and set(args.assets) != set(config.symbols):
        config.portfolios = {}  # default examples are not compatible with arbitrary CLI assets
    if args.strict:
        config.strict = True
    if args.refresh_cache:
        config.refresh_cache = True
    run(config)


if __name__ == "__main__":
    main()
