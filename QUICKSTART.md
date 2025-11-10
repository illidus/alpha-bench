# Quick Start Guide

Get alpha-bench running in **5 minutes** or less!

---

## Prerequisites

- Python 3.10+
- API keys ready:
  - Anthropic Claude API key ([get here](https://console.anthropic.com/))
  - Market data API key (e.g., Alpha Vantage, Yahoo Finance)

---

## 1. Setup (2 minutes)

```bash
# Navigate to project
cd /c/dev/alpha-bench

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure API keys
cp .env.example .env
# Edit .env and add your keys:
#   ANTHROPIC_API_KEY=your_key_here
#   MARKET_DATA_API_KEY=your_key_here
```

---

## 2. Run Your First Benchmark (2 minutes)

```bash
# Run a manual benchmark with Claude Code
python scripts/run_benchmark.py \
    --model claude-code-numeric \
    --lookback 72h \
    --forecast 24h \
    --symbol BTC/USD
```

Expected output:
```
[INFO] Fetching market data for BTC/USD...
[INFO] Generating features (EMA, MACD, RSI)...
[INFO] Running simulation with claude-code-numeric...
[INFO] Simulation complete!

Results:
  PnL: $127.50
  Sharpe Ratio: 1.42
  Max Drawdown: -2.1%
  Trades: 8 (5 wins, 3 losses)

Results saved to: results/2025-11-10T12:00Z/claude-code-numeric/
```

---

## 3. View Results (1 minute)

### Option A: Dashboard (Recommended)
```bash
streamlit run alpha_bench/dashboard/app.py
# Open browser to http://localhost:8501
```

### Option B: Command Line
```python
import pandas as pd

# View benchmark results
df = pd.read_parquet('results/benchmarks.parquet')
print(df[['model_id', 'pnl', 'sharpe', 'max_dd']])

# View trading decisions
decisions = pd.read_parquet('results/2025-11-10T12:00Z/claude-code-numeric/decisions.parquet')
print(decisions[['timestamp', 'action', 'confidence', 'rationale']].head())
```

---

## 4. Set Up Automated Runs (Optional)

For recurring benchmarks every 6 hours:

```bash
# Initialize Airflow
export AIRFLOW_HOME=$(pwd)/airflow_home
export AIRFLOW__CORE__DAGS_FOLDER=$(pwd)/alpha_bench/airflow_dags
airflow db init

# Start Airflow
airflow scheduler &
airflow webserver &

# Access UI at http://localhost:8080
# Username: admin, Password: admin (set during init)
```

---

## Next Steps

### Add More Models
Edit `configs/models.yaml`:
```yaml
models:
  - id: my-custom-model
    provider: claude_code
    system_prompt: sys_custom.txt
    features: [price, ema, rsi]
    schedule: 6h
    risk_cap: 0.01
```

### Customize Prompts
Create `prompts/sys_custom.txt`:
```
You are a quantitative trading assistant...
[Your instructions here]
```

### Run Tests
```bash
pytest --cov=alpha_bench
```

---

## Troubleshooting

**"Module not found" errors**:
- Ensure virtual environment is activated
- Run `pip install -r requirements.txt` again

**API key errors**:
- Check `.env` file has correct keys
- Verify keys are not expired

**No market data**:
- Check `MARKET_DATA_API_KEY` is set
- Verify API endpoint is accessible

**Airflow issues**:
- Check `AIRFLOW__CORE__DAGS_FOLDER` points to `alpha_bench/airflow_dags`
- Run `airflow dags list` to see if DAG is detected

---

## Learn More

- **[README.md](README.md)** - Full documentation
- **[CLAUDE.md](CLAUDE.md)** - Development guide
- **[docs/](docs/)** - Architecture and API reference

---

**You're all set! Start experimenting with LLM trading strategies!** 🚀
