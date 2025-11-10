---
description: "Analyze benchmark results and generate insights"
---

# Analyze Benchmark Results

Analyze benchmark results from a specific run or compare multiple runs to generate insights and recommendations.

## Usage

```
/analyze <run_id|"latest"|"all">
```

## Steps

1. **Load results**
   - If `latest`: Load most recent run from `results/benchmarks.parquet`
   - If `<run_id>`: Load specific run data
   - If `all`: Load all runs for comparative analysis

2. **Aggregate metrics**
   - Load decisions, simulation results, and metrics for each model
   - Calculate summary statistics
   - Identify outliers and anomalies

3. **Generate comparative analysis**
   - Compare models side-by-side
   - Rank by Sharpe ratio, PnL, and other metrics
   - Identify best/worst performers

4. **Feature importance analysis**
   - Correlate features with PnL
   - Identify which features drive performance
   - Suggest feature engineering improvements

5. **Generate visualizations** (optional)
   - Equity curves
   - Drawdown charts
   - Win rate by model
   - Feature importance heatmap

6. **Provide recommendations**
   - Which models to deploy
   - Which prompts to iterate on
   - Which features to add/remove
   - Risk management suggestions

## Example Output

```
[INFO] Analyzing run: 2025-11-10T12:00Z

Models Analyzed: 3
  - claude-code-numeric
  - claude-code-text
  - baseline-trend-following

=== Performance Ranking ===

Rank | Model                    | PnL    | Sharpe | Max DD | Win Rate
-----|--------------------------|--------|--------|--------|----------
1    | claude-code-text         | $156.20| 1.67   | -1.8%  | 66.7%
2    | claude-code-numeric      | $127.50| 1.42   | -2.1%  | 62.5%
3    | baseline-trend-following | $45.30 | 0.89   | -4.2%  | 55.0%

=== Key Insights ===

✅ **Text features add value**
   - claude-code-text outperforms claude-code-numeric by 22.5%
   - Sentiment features correlate positively with PnL (r=0.42)
   - Recommendation: Enable text features for all models

⚠️  **Baseline underperforming**
   - Simple EMA crossover strategy has lower Sharpe
   - Higher drawdown (-4.2% vs -2.1%)
   - Recommendation: Consider more sophisticated baselines

📊 **Feature Importance** (top 5)
   1. sentiment_news (importance: 0.28)
   2. rsi_14 (importance: 0.22)
   3. macd_hist (importance: 0.19)
   4. ema_12 (importance: 0.15)
   5. volume_sma_20 (importance: 0.12)

💡 **Recommendations**
   1. Deploy claude-code-text to production schedule
   2. Add more sentiment sources (Twitter, Reddit)
   3. Experiment with longer EMA periods (50, 200)
   4. Increase position size for high-confidence signals
   5. Review prompts for baseline model

=== Next Steps ===

- View detailed dashboard: streamlit run alpha_bench/dashboard/app.py
- Run extended backtest: /benchmark claude-code-text --lookback 720h
- Update model config: vi configs/models.yaml
- Export training data: python scripts/export_training_data.py
```

## Advanced Usage

```
# Analyze last 7 days
/analyze last-7d

# Compare two specific models
/analyze --compare claude-code-numeric,claude-code-text

# Focus on specific metrics
/analyze latest --metrics sharpe,sortino,calmar

# Export to CSV
/analyze latest --export results/analysis_2025-11-10.csv
```
