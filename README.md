# Multi-market total-return research

[Open in Colab](https://colab.research.google.com/github/hh4832/compare_stock_return/blob/main/notebooks/compare_stock_return_colab.ipynb)

Compare Taiwan stocks/ETFs (FinLab) and US stocks/ETFs (Tiingo) with explicit identifiers:
`TW:0050`, `TW:009816`, `TW:0056`, `US:VOO`, `US:VGT`.

**Cross-market returns are measured in each asset's local currency. FX effects are intentionally excluded.**
Taiwan returns are TWD local-currency returns; US returns are USD local-currency returns.
Only percentage returns and risk metrics are compared. No USD/TWD conversion, FX attribution or actual TWD wealth NAV is implemented. `fx_mode` must be `none`; other values raise NotImplementedError.

## Run

Python >=3.10. Install `requirements.txt`, then run:

```bash
python scripts/run_compare.py --assets TW:0050 TW:009816 US:VOO US:VGT --benchmark TW:0050 --date-mode intersection --return-type total_return --fx-mode none
python -m pytest -q
```

The output folder must already exist. Default:
`/content/drive/MyDrive/00Quant_Research/compare_stock_return`
CLI `--output-root` explicitly selects another existing local folder. Portfolio examples load from YAML; overriding the asset list clears incompatible default portfolio examples. Supply a matching YAML for custom portfolios.
Colab clones/pulls latest repo, installs dependencies, explicitly resolves `src`, mounts Drive, checks provider credentials, runs the same pipeline, and displays asset metadata, headline metrics, model portfolios and charts. Notebook only configures/executes/displays.

Credentials are only environment variables or Colab Secrets: `FINLAB_API_TOKEN`, `TIINGO_API_TOKEN`.
Never place credentials in YAML, notebook, metadata or output. Tiingo uses Authorization headers, bounded request timeout and sanitized failures. No Tiingo SDK dependency is needed; the client uses requests.

## Provider methodology

FinLab preserves `price:收盤價` → raw_close, `etl:adj_close` → adjusted_close.
Tiingo EOD preserves `close`, `adjClose`, `divCash`, `splitFactor`; maps close/adjClose to raw_close/adjusted_close.
Total return = adjusted_close.pct_change(fill_method=None), price return = raw_close.pct_change(fill_method=None).
Dividend/split fields are audit evidence only, never added to adjusted-price returns.
FinLab corporate-action event data is unavailable in this contract; no events are invented. `corporate_actions.parquet` contains Tiingo audit fields (all source sessions), or an empty typed-column table when none are available.
Source contracts: [FinLab adjusted prices](https://finlab.finance/docs/details/market_customization/), [Tiingo EOD](https://www.tiingo.com/documentation/end-of-day).
Provider adjustment is a total-return proxy; individual actions, reinvestment transactions and investor taxes are not independently reconstructed. Raw price returns may contain split jumps. Observed expenses are already reflected in ETF prices; fees remain references unless an explicit additional synthetic scenario is requested.

## Market calendars and comparison windows

Common calendar start = max(each first usable date), end = min(each last usable date).
Each asset retains **all its own observations inside that window**, including dates when the other market is closed. Different observation counts are allowed. No intersection across markets, ffill/bfill, synthetic zero returns or invented prices.
Each metric records its actual first/last observed dates alongside common calendar boundaries. When a boundary is a holiday in one market, its first/last observation is inside the window; no stale boundary price is manufactured. CAGR uses those actual observation dates, with that small endpoint difference explicitly visible.

Provider frames must have sorted unique DatetimeIndex and positive finite prices. Internal missing raw/adjusted prices are fatal except explicit date-specific suspension/non-trading evidence. Tiingo returned sessions with missing prices, including boundary rows, fail. **Tiingo missing session rows are not independently verified against an exchange calendar in this first version**; provider-returned sessions are the observation contract. Another market's dates never determine missing sessions. Entire missing months in a model portfolio fail.
0050 known suspensions (2025-06-11/12/13/16/17) are centrally configured as `market_suspension`; unexplained gaps remain fatal. Large suspensions can distort annualization at 252 observations/year.

`intersection` means common calendar window. `custom` limits this headline window (strict rejects out-of-range requests). Full history remains supplementary and visibly warns about incomparable periods. Every pair retains its own maximum common calendar window, independently of newer assets/custom headline windows.

## Relative analytics

Same market pairs: daily correlation, OLS beta/alpha/R², tracking error, information ratio, captures and monthly excess statistics. Relative prices are inner-joined before returns, never stale returns joined afterwards. Classified `same_market_daily`.
Cross market pairs: **no daily regression, alpha, beta, tracking error or information ratio**. Classified `cross_market_monthly` and `CROSS_MARKET_DAILY_ALIGNMENT_NOT_IMPLEMENTED`.
Compute monthly correlation/covariance using each market's compounded monthly returns and only jointly complete calendar months. Positive/downside month co-movement is the fraction of common months where both returns are positive/negative. Boundary months are conservatively excluded. Monthly alignment reduces session timing mismatch; it does not assert synchronized closing instants.

## Model portfolios

YAML `portfolios` maps portfolio names to asset weights. Finite nonnegative weights must satisfy abs(sum-1)<1e-8. Each complete common month uses sum(weight × component monthly return); target weights reset every month. No missing-month fill, leverage, costs, taxes or FX.
These are **local-currency model portfolio returns**, not actual TWD wealth returns.
Portfolio NAV compounds modeled monthly returns from 100; volatility/Sharpe/Sortino annualize with 12, CAGR uses elapsed full months, MDD uses monthly observations (intramonth losses are not visible). Best/worst year use 12 complete months; rolling 12M requires 12 months. No complete common month raises a clear error; very new ETFs cannot support a monthly portfolio yet.

## Outputs / reproducibility

Root retains `runs/YYYYMMDD_HHMMSS_<unique>/`, `latest/`, and `cache/finlab/`, `cache/tiingo/`.
Only successful runs promote latest via staged copy/rename and rollback. Historical outputs are never modified. Single writer per root; Drive rename is not distributed atomicity.

`results/`: summary_metrics, intersection_metrics, full_history_metrics, pairwise_metrics, benchmark_metrics, cross_market_monthly_metrics, monthly_returns (long/wide), annual_returns (long/wide), drawdowns, rolling_metrics, model_portfolio_metrics, model_portfolio_monthly_returns, model_portfolio_annual_returns, data_quality_report, assets, fees, plus existing monthly_excess/synthetic_fee/optional holdings outputs (CSV).
`data/`: source_prices, aligned_prices (own-market dates), returns, corporate_actions (Parquet).
`charts/`: local-currency equity, underwater, rolling returns/volatility/Sharpe and model portfolio equity/drawdown, HTML and PNG.
Metadata records provider provenance, explicit identifiers/market/currency/provider, common boundaries and per-asset observation counts, pair classifications, FX none, model assumptions, source freshness, environment versions, git SHA and checksums. No credentials.
Cache defaults USE_CACHE=True/REFRESH_CACHE=False and 24-hour TTL. Expired entries trigger fresh download; no stale fallback. Tiingo cache identity includes provider, ticker, endpoint, full requested date range; download timestamp is stored and checked in sidecar metadata. A refresh downloads full history to incorporate changed adjustments. last_dataset_date reveals provider latency.

## Migration / extensions

Old: `SYMBOLS = ["0050", "009816"]`; new: `ASSETS = ["TW:0050", "TW:009816"]`.
Config.assets is the primary interface. Config.symbols/CLI --symbols is an explicit legacy Taiwan-only layer, retained for old custom NAV workflows; the identifier parser itself never guesses markets. Use prefixed keys throughout fees, holdings_files, custom_assets and non_trading_dates when using assets. Custom NAV requires total_return_confirmed=true and a dated sourced CSV. Holdings remain optional dated user-supplied snapshots; absent metadata is unknown rather than guessed.

Architecture: providers normalize data; data_loader dispatches; alignment/returns/metrics/rolling/benchmark/cross_market/model_portfolio implement calculations; pipeline/reporting export and audit. All unit tests are offline with mock providers. Live FinLab/Tiingo validation requires user credentials and has not been claimed. No pre-launch ETF reconstruction, point-in-time strategy reconstruction or future FX implementation is supplied.

## Metrics and definitions

- CAGR = (end/start) ** (365.25 / calendar_days) - 1。
- Volatility = sample daily std × sqrt(252)；risk-free daily = (1+annual_rf) ** (1/252)-1。
- Sharpe = mean daily excess × 252 / volatility。
- Sortino = mean daily excess × 252 / (sqrt(mean(min(excess,0)^2)) × sqrt(252))。
- MDD = min(price / cumulative_max(price) - 1)；Calmar = CAGR / abs(MDD)。
- Undefined ratios return NaN；無 drawdown MDD=0，Calmar=NaN。
- Drawdown episodes：peak→trough→recovery，最差 10 個（不足 10 個不偽造）；天數為 calendar days。
  未恢復 episode recovery=null，underwater duration 計至樣本終點。
- Rolling returns：1/3/6/12/36/60 calendar months，以 horizon date 當日或之前的最近觀察為基準；
  36/60M 依實際 calendar days 年化。資料不足 NaN。
- Rolling risk：12M=252、36M=756 return observations（21 sessions/month approximation）；rolling 12M MDD=252 price observations。
- Annual/monthly：複利每日報酬，邊界期間保守標記 partial_period；最佳/最差年度只取完整內部年度。
  best/worst month 可包含 partial，CSV 有旗標。年度寬表旗標請對照 long 表。
- Relative：先 inner join **價格** 再算兩方 return。
  cumulative excess 是累積報酬差（percentage points），excess CAGR 是 CAGR 差；
  annualized excess = mean daily (asset-benchmark) ×252；tracking error=sample excess std ×sqrt(252)。
  Information ratio = annualized arithmetic excess / tracking error；beta/alpha/R² 使用 OLS，
  alpha = daily intercept ×252，alpha p-value 使用 Newey-West HAC (maxlags<=5)。
  Upside/downside capture = 該組 benchmark 正／負日的 asset 複利報酬 / benchmark 複利報酬。
  Monthly excess 統計只使用兩方完整月份；部分月份仍輸出並標記。
  不顯著結果不得寫成明顯優勝，短樣本不作穩健 alpha 結論。
