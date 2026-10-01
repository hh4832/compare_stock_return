# Taiwan Stock / ETF Total Return Comparison

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/hh4832/compare_stock_return/blob/main/notebooks/compare_stock_return_colab.ipynb)

可輸入任意多個台股股票、上市／上櫃 ETF，或自訂 NAV。預設比較 **0050、009816**；
新增 006208、2330 只需修改 notebook 最前面的 USER CONFIG。
DISPLAY_SYMBOLS 只改圖表，所有標的仍參與 global、full-history、pairwise 計算與輸出。

## Colab

1. 開啟上方 notebook，修改 USER CONFIG，Run All。
2. 在 Colab Secrets 新增 `FINLAB_API_TOKEN` 並授權 notebook 使用。
3. Drive 授權是互動式操作；先建立以下 exact folder，缺少時明確報錯，不另存他處。

`/content/drive/MyDrive/00Quant_Research/compare_stock_return`

Notebook 會 clone、install、import、mount、authenticate、列出環境，執行同一 pipeline，展示共同期間主表及圖表。
乾淨 runtime 不需要手動建立 Python 路徑。需要 FinLab 帳戶方案對應的資料權限。
[0050 vs 009816 research notebook](notebooks/research_0050_vs_009816.ipynb) 使用同一引擎，展示風險、超額報酬、drawdown、費用及可選 holdings。

## Local / CLI

Python >=3.10。建議虛擬環境：

```bash
python -m pip install -r requirements.txt
python -m pip install -e .
# FINLAB_API_TOKEN should be injected through your environment, never put it in a file.
python scripts/run_compare.py --symbols 0050 009816 006208 --benchmark 0050 --output-root /your/existing/output/folder
python -m pytest -q
```

CLI 支援 --config、--date-mode、--start、--end、--strict、--return-type、--refresh-cache。
正式 Drive 預設路徑固定；--output-root 可供本機或測試明確指定。

## Return accounting / verified provider contract

主要 total_return = `etl:adj_close.pct_change(fill_method=None)`，price_return =
`price:收盤價.pct_change(fill_method=None)`。normalized NAV = 100 × price / first price。
FinLab 官方文件說明 adjusted price 包含配息、配股、分割；官方說明另涵蓋除權息、增減資。
直接使用 provider adjustment，**不再額外加現金股息或股票股利**。

Primary references (checked 2026-10-01):
- https://finlab.finance/docs/details/market_customization/
- https://finlab.finance/blog/finlab-backtest-return-calculation
- https://finlab.finance/blog/event-study-usage
- https://finlab.finance/data/dividends

這是 provider-adjusted total-return proxy，並非逐筆 corporate-action、現金流及再投資交易重建。
現金股利、股票股利、分割、減資與 ETF distribution 依賴 FinLab 實際資料品質；
個別事件未經本程式獨立重建，不聲稱完全等同投資者可實現稅後報酬。
原始 close price return 跨分割可能出現大幅跳空，只是原始價格變化，不能解讀為投資損失。
「不配息」本身不代表 alpha。0050 含息再投資 proxy 才能公平比較 009816。
0050 不配息連結基金有自己的 NAV、費用與追蹤誤差，**本專案不把 0050 ETF 當成該基金實際 NAV**。

## Date and missing-data contract

每個標的取得 first/last valid date；global start = max(first)，end = min(last)，
再取完整價格觀察日期交集。所有 headline metrics 使用相同觀察日期。
所有資產完整歷史另存 full_history_metrics；不同期間明確標記
`NOT DIRECTLY COMPARABLE DUE TO DIFFERENT DATE RANGES`。

- intersection：預設正式公平比較。
- full_history：各自完整歷史，supplementary，不作公平勝負結論。
- custom：strict=false 調整到資料交集；strict=true 拒絕超出任一資產涵蓋期間。
- pairwise：每一 unordered pair 用自己的完整交集，不被其他新標的縮短。
  benchmark metrics 同樣保留各自 pairwise 日期；日期及 calendar exclusion 均輸出。
  Custom 只限制 headline，pairwise 始終完整歷史。

在持有區間內缺任一 raw/adjusted 價格預設失敗，禁止任何 silent fill。
市場日曆各自休市、停牌與 provider 缺值不能只靠 NaN 判定：
`non_trading_dates` 需明確 date→`market_suspension` / `legitimate_non_trading` 證據配置。
有證據的日期才可排除，無證據 provider gap fatal。排除後是跨觀察點報酬，
年度 252 次風險換算在大量停牌時可能失真；metadata 保留 exclusion count。
上市前／下市後 NaN 不填補。共同價格 <2 筆 fatal，<60 筆 warning；<1 年 CAGR 標記可能失真。

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

## Configuration extensions

`config/default.yaml` 是完整預設；YAML ticker 一律加引號，保留前導零。

```yaml
symbols: ["0050", "006208", "2330", "MY_NAV"]
benchmark: "0050"
display_symbols: ["0050", "MY_NAV"]
custom_assets:
  MY_NAV:
    path: /path/nav.csv
    name: My accumulation fund
    source: official NAV export
    total_return_confirmed: true
fees:
  "0050":
    annual_expense_ratio: 0.001
    source: user supplied reference; verify actual fee
    apply_synthetic: false
```

Custom CSV：date,raw_close,adjusted_close；非配息 NAV 只有經確認含息意義才可用相同數值。
Fees 預設僅 reference，**不改 historical observed return**。
顯式 apply_synthetic=true 才產生 synthetic_fee_metrics，按 calendar time 扣除 additional fee；
already_included=true 拒絕再扣。
Optional holdings_files：symbol→CSV，需 ticker,weight (fraction sum=1),as_of_date,source。
可算 concentration/HHI/effective count、Jaccard overlap/weighted overlap，跨日期標記不可直接比較。
尚未確認可靠的 FinLab holdings endpoint，因此預設 graceful skip，使用者可供官方 dated snapshots。
未知 asset name/type 明確 unknown，不猜 ticker 分類。原始 return 比較不因 metadata 缺少而中止。

## Outputs and reproducibility

`runs/YYYYMMDD_HHMMSS_<unique>/` 下有 config/data/results/charts/logs/metadata，
`latest/` 是最近成功 run 的 staged copy；失敗 run 保留 stage/error type，不覆蓋 latest。
同秒執行以 UUID 防 collision；不使用 symlink。避免多個 process 同時寫同一 Drive root。
Drive mount rename 不保证 distributed atomicity，單一 writer 為本版本契約。

保存 source/aligned prices、兩種每日 return、summary/full/intersection/pairwise/benchmark、
annual/monthly long+wide、monthly excess、drawdowns、rolling、fees、data quality、assets，
所有 7 個圖表均 HTML+PNG。HTML 自含 Plotly，不依賴外部 CDN。
Metadata 記錄 UTC timestamp、runtime、Python/packages、git SHA、config、provenance、期間及檔案 SHA256。
Parquet cache 按 dataset+symbols 分開；記錄 downloaded_at，預設 24h TTL，逾期重抓。
refresh_cache=true 強制重抓；cache 不代表即時，來源更新延遲以 last_dataset_date 揭示。
版本範圍寫 requirements，實際 run package_versions 可重建當次環境；不是鎖檔。
Outputs/data/cache 不進 git，無 token 寫入 config/output。進度由單一 tqdm.auto stage bar 管理。

## Architecture / limitations / future

src 模組：config、data_loader、symbol_resolver、validation、alignment、returns、metrics、drawdown、
rolling、benchmark、regression、fees、holdings、plotting、reporting、progress、pipeline。
notebooks 只 configure/execute/display，scripts/run_compare.py 使用同一 engine。
Unit tests 全部 synthetic 無網路。實際 FinLab 需 token，無 token 不宣稱完成 live integration。

009816 比較僅實際有資料期間，絕不 backfill。strategies/ 預留官方 methodology 經確認後的
point-in-time market-cap/profitability/momentum reconstruction；目前沒有重建策略，
不捏造官方 6M/12M momentum formula。不包含投資者稅、交易費與 dividend reinvestment friction。
