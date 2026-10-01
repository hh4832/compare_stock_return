"""CLI entry point to the same pipeline as Colab."""

import argparse

from compare_stock_return.config import Config
from compare_stock_return.pipeline import run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/default.yaml")
    parser.add_argument("--symbols", nargs="+")
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
    if args.strict:
        config.strict = True
    if args.refresh_cache:
        config.refresh_cache = True
    run(config)


if __name__ == "__main__":
    main()
