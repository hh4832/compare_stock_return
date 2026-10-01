# Canonical agent instructions
Purpose: reusable Taiwan stock/ETF total-return research, never a hard-coded pair.
Architecture: src/compare_stock_return holds all calculations; notebooks configure/display,
CLI shares pipeline. FinLab is primary; explicitly confirmed custom NAV is secondary.
Read this file before edits. AGENT.md is only a pointer.

- Authenticate only with Colab Secrets/environment FINLAB_API_TOKEN. Never print, commit,
  serialize credentials or exception payloads that can contain credentials.
- Use etl:adj_close directly for provider-adjusted total-return proxy; never add dividends again.
  Observed fund prices already incorporate fund operating expenses; never deduct twice.
- Headline comparisons use identical global intersection dates; full history has a warning.
  Pairwise metrics use their own longer intersection, aligned prices before returns.
- No look-ahead, inferred pre-launch series, invented index rules, ffill/bfill or zero returns.
- Missing prices fail unless date-specific suspension/non-trading evidence is explicitly supplied.
  Never label unexplained gaps as holidays. Record calendar exclusions and data quality.
- Default output root is /content/drive/MyDrive/00Quant_Research/compare_stock_return.
  Root must exist. Never modify historical runs/raw output; create a unique run each time.
  latest is published only after SUCCESS, via staged copy/rename and rollback, never symlinks.
- pytest and git diff --check must pass before commit. Never force push.
- Add a metric in metrics.py/rolling.py, document formula and write synthetic numerical tests.
- Add a provider through data_loader.load contract (assets, metadata, provenance), not notebooks.
- Add an asset via Config.symbols; custom NAV must explicitly confirm adjustment accounting.
- Use type hints, docstrings, pathlib, isolated logger handlers, central constants, no giant notebook.
- Record config, source prices/hash, dataset freshness, versions, git SHA, windows and checksums.
  Unit tests are offline; integration tests require opt-in credentials and may skip.
- Holdings are optional dated sourced snapshots; malformed/unavailable holdings must not block returns.
