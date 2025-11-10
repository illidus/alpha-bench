---
description: "Run a manual benchmark simulation"
---

# Run Manual Benchmark

Run a manual benchmark simulation for model testing and validation.

## Usage

```
/benchmark <model_id> [options]
```

## Steps

1. **Validate model exists**
   - Check `configs/models.yaml` for the specified model_id
   - Verify system prompt file exists in `prompts/`

2. **Fetch latest market data**
   - Use `alpha_bench.data.loader.MarketDataLoader`
   - Default lookback: 72 hours
   - Symbols: BTC/USD (or user-specified)

3. **Generate features**
   - Use `alpha_bench.data.features.FeatureEngineer`
   - Generate all features specified in model config
   - Save to `data/runs/{date}/features.parquet`

4. **Run simulation**
   - Load model via `alpha_bench.models.registry.ModelRegistry`
   - Initialize `alpha_bench.simulation.engine.SimulationEngine`
   - Execute paper trading simulation

5. **Calculate metrics**
   - Use `alpha_bench.metrics.calculator.MetricsCalculator`
   - Compute PnL, Sharpe, Sortino, Max Drawdown, etc.
   - Save results to `results/{run_id}/{model_id}/`

6. **Display results**
   - Show summary metrics in table format
   - Provide path to detailed results
   - Suggest next steps (view in dashboard, compare with other models)

## Example

```bash
python scripts/run_benchmark.py \
    --model claude-code-numeric \
    --lookback 72h \
    --forecast 24h \
    --symbol BTC/USD
```

## Output

```
[INFO] Starting benchmark for model: claude-code-numeric
[INFO] Fetching market data...
[INFO] Generating features...
[INFO] Running simulation...
[INFO] Calculating metrics...

Results Summary:
  Model: claude-code-numeric
  Period: 2025-11-09 12:00 to 2025-11-10 12:00
  Symbol: BTC/USD

  Performance:
    PnL: $127.50 (+1.28%)
    Sharpe Ratio: 1.42
    Sortino Ratio: 1.89
    Max Drawdown: -2.1%

  Trading Activity:
    Total Trades: 8
    Win Rate: 62.5% (5 wins, 3 losses)
    Avg Holding Time: 4.2 hours
    Turnover: 0.85

  Results saved to: results/2025-11-10T12:00Z/claude-code-numeric/

Next steps:
  - View in dashboard: streamlit run alpha_bench/dashboard/app.py
  - Compare models: /analyze latest
  - Run all models: airflow dags trigger benchmark_pipeline
```
