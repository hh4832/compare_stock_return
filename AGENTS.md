# Canonical agent instructions
Purpose: reusable Taiwan/US stock/ETF local-currency total-return research, never a hard-coded pair.
Architecture: src/compare_stock_return holds all calculations; notebooks configure/display,
CLI shares pipeline. FinLab supplies Taiwan; Tiingo supplies US; explicitly confirmed custom NAV is secondary.
Read this file before edits. AGENT.md is only a pointer.

- Authenticate only with Colab Secrets/environment FINLAB_API_TOKEN. Never print, commit,
  serialize credentials or exception payloads that can contain credentials.
- Use etl:adj_close directly for provider-adjusted total-return proxy; never add dividends again.
  Observed fund prices already incorporate fund operating expenses; never deduct twice.
- Headline comparisons use common calendar windows and each market's own observations.
  Never delete another market's sessions to fabricate daily synchronization.
  Pairwise uses its own longer calendar window; full history has a warning.
- No look-ahead, inferred pre-launch series, invented index rules, ffill/bfill or zero returns.
- Missing-data policy defaults to warn; error rejects unexplained gaps, ignore continues without warning logs.
  All policies preserve reports/metadata, never fill/zero returns or label unknown gaps as holidays.
  Invalid/non-positive/non-finite prices, entirely missing assets and malformed/duplicate indexes stay fatal.
  Export missing_data_details.csv and propagate DAILY_METRICS_HAVE_MISSING_SESSION_WARNING through
  summary, rolling and same-market pairwise/benchmark outputs when gaps are unexplained.
  Audit excluded sessions and returns spanning missing observations; never describe them as normal daily returns.
- Default output root is /content/drive/MyDrive/00Quant_Research/compare_stock_return.
  Root must exist. Never modify historical runs/raw output; create a unique run each time.
  latest is published only after SUCCESS, via staged copy/rename and rollback, never symlinks.
- pytest and git diff --check must pass before commit. Never force push.
- Add a metric in metrics.py/rolling.py, document formula and write synthetic numerical tests.
- Add a provider through data_loader.load contract (assets, metadata, provenance), not notebooks.
- Add an asset via explicit Config.assets market:ticker identifiers; custom NAV must explicitly confirm adjustment accounting.
- Use type hints, docstrings, pathlib, isolated logger handlers, central constants, no giant notebook.
- Record config, source prices/hash, dataset freshness, versions, git SHA, windows and checksums.
  Unit tests are offline; integration tests require opt-in credentials and may skip.
- Holdings are optional dated sourced snapshots; malformed/unavailable holdings must not block returns.

- Providers implement the normalized frame/metadata/provenance contract under providers/.
- TIINGO_API_TOKEN only from environment/Colab Secrets, never print/log/serialize token or HTTP payloads.
- Tiingo adjusted close includes provider adjustments. divCash/splitFactor are audit only.
- Market calendars are independent. Never use other markets to infer missing sessions.
  The current Tiingo provider-returned-session limitation must stay explicit until independent calendar coverage is implemented.
- Cross-market daily close timestamps are not synchronous. No daily alpha/beta/TE/IR.
  Cross-market relative analytics use complete monthly returns only; preserve status labels.
- FX_MODE must remain none; reject other modes until explicitly implemented later.
- Model portfolios reset target weights monthly; sum(weights)=1 within strict 1e-8 tolerance.
  Only complete common months, no gaps/fill. Use monthly (12/year) risk scaling and monthly MDD.
  Label local-currency model portfolio / FX excluded; never actual TWD wealth.
