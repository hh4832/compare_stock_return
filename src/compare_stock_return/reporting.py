"""Immutable run directories; staged latest publication with rollback."""

import hashlib
import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys
import uuid
from pathlib import Path


def json_write(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, default=str, allow_nan=False)
    )


def environment() -> dict:
    packages = {}
    for name in [
        "compare-stock-return",
        "finlab",
        "pandas",
        "numpy",
        "scipy",
        "matplotlib",
        "plotly",
        "statsmodels",
        "pyarrow",
        "PyYAML",
        "tqdm",
        "requests",
    ]:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = "not installed"
    try:
        git = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        git = None
    return dict(
        python=sys.version,
        platform=platform.platform(),
        git_commit=git,
        packages=packages,
    )


def promote_latest(run: Path, root: Path) -> None:
    stage = root / f".latest-{uuid.uuid4().hex}"
    backup = root / f".previous-{uuid.uuid4().hex}"
    latest = root / "latest"
    shutil.copytree(run, stage)
    moved = False
    try:
        if latest.exists():
            latest.rename(backup)
            moved = True
        stage.rename(latest)
    except Exception:
        if moved and not latest.exists():
            backup.rename(latest)
        if stage.exists():
            shutil.rmtree(stage)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def checksums(run: Path) -> dict:
    return {
        str(f.relative_to(run)): hashlib.sha256(f.read_bytes()).hexdigest()
        for f in sorted(run.rglob("*"))
        if f.is_file() and f.name != "checksums.json"
    }
