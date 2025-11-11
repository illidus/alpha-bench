# Alpha-Bench Setup Guide

This guide will walk you through everything you need to get alpha-bench up and running with real data.

## Quick Start Checklist

- [ ] Python 3.10+ installed
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] `.env` file configured with API keys
- [ ] Choose a market data provider
- [ ] Run a test benchmark with mock data
- [ ] (Optional) Set up Airflow for automated runs
- [ ] (Optional) Launch dashboard

---

## 1. Prerequisites

### System Requirements

- **Python**: 3.10 or higher
- **Disk Space**: At least 1GB for data and results
- **RAM**: Minimum 4GB (8GB recommended for Airflow)
- **OS**: Linux, macOS, or Windows (with WSL recommended)

### Required Accounts & API Keys

You'll need API keys for the following services:

#### **Required:**

1. **Anthropic Claude API** (for Claude Code models)
   - Sign up at: https://console.anthropic.com/
   - Navigate to API Keys section
   - Create a new API key
   - Cost: ~$0.003 per 1K tokens (very affordable for testing)

2. **Market Data Provider** (choose one):

   **Option A: CoinAPI (Recommended for crypto)**
   - Sign up at: https://www.coinapi.io/
   - Free tier: 100 requests/day
   - Paid tiers available for production use
   - Best for: BTC, ETH, and other cryptocurrencies

   **Option B: Alpha Vantage (Good for stocks & forex)**
   - Sign up at: https://www.alphavantage.co/support/#api-key
   - Free tier: 5 requests/minute, 500 requests/day
   - Best for: US stocks, forex, crypto
   - Limitation: Rate limits are strict on free tier

   **Option C: Yahoo Finance (via yfinance)**
   - No API key required!
   - Install: `pip install yfinance`
   - Free but unofficial (may have reliability issues)
   - Best for: Quick testing, US stocks

   **Option D: Mock Data (for testing only)**
   - No API key needed
   - Generates realistic synthetic data
   - Use this to test the system before committing to a paid provider

#### **Optional:**

- **llama.cpp models** (for local LLM inference)
  - Download GGUF models from Hugging Face
  - Example: https://huggingface.co/TheBloke
  - No API key needed, but requires model file (~4-7GB)

---

## 2. Installation

### Step 1: Clone and Navigate

```bash
cd /c/dev  # Or your preferred directory
git clone <your-repo-url> alpha-bench
cd alpha-bench
```

### Step 2: Create Virtual Environment

```bash
python -m venv venv

# Activate (choose your OS)
source venv/bin/activate              # Linux/macOS
venv\Scripts\activate                 # Windows CMD
source venv/Scripts/activate          # Windows Git Bash
```

### Step 3: Install Dependencies

```bash
# Core dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Development dependencies (for testing)
pip install -r requirements-dev.txt

# Optional: llama.cpp support
pip install llama-cpp-python
```

---

## 3. Configuration

### Step 1: Create .env File

```bash
cp .env.example .env
```

### Step 2: Edit .env with Your API Keys

Open `.env` in your editor and configure:

#### **Minimum Required Settings:**

```bash
# Anthropic API Key (REQUIRED for Claude models)
ANTHROPIC_API_KEY=sk-ant-your-actual-key-here

# Market Data Provider (CHOOSE ONE)

# Option A: CoinAPI
MARKET_DATA_API_KEY=your-coinapi-key-here
MARKET_DATA_BASE_URL=https://rest.coinapi.io/v1

# Option B: Alpha Vantage
# MARKET_DATA_API_KEY=your-alphavantage-key-here
# MARKET_DATA_BASE_URL=https://www.alphavantage.co

# Option C: Mock Data (no key needed)
# Just leave above fields commented out and set provider=mock in code
```

#### **Recommended Settings:**

```bash
# Benchmark defaults
DEFAULT_LOOKBACK_HOURS=72      # 3 days of data
DEFAULT_FORECAST_HOURS=24      # 1 day forecast
INITIAL_CAPITAL=10000          # $10,000 starting capital
DEFAULT_RISK_CAP=0.01          # 1% max risk per trade

# Airflow (if using automated runs)
AIRFLOW_HOME=/c/dev/alpha-bench/airflow_home
AIRFLOW__CORE__DAGS_FOLDER=/c/dev/alpha-bench/alpha_bench/airflow_dags
```

### Step 3: Update Market Data Provider in Code

Edit `alpha_bench/data/loader.py` or pass provider in your scripts:

```python
# For CoinAPI
loader = MarketDataLoader(provider="coinapi")

# For Alpha Vantage
loader = MarketDataLoader(provider="alphavantage")

# For Yahoo Finance
loader = MarketDataLoader(provider="yahoo")

# For Mock Data (testing)
loader = MarketDataLoader(provider="mock")
```

Or update the DAG files to use your preferred provider.

---

## 4. Test Your Setup

### Option A: Quick Test with Mock Data (No API Keys Needed)

```bash
# This uses mock data, so no API keys are required
python scripts/run_benchmark.py \
    --model baseline-trend-following \
    --lookback 72h \
    --forecast 24h \
    --symbol BTC/USD
```

Expected output:
```
Benchmark Results - baseline-trend-following
============================================================
Symbol: BTC/USD
...
Total Return: X.XX%
Sharpe Ratio: X.XX
Number of Trades: X
```

### Option B: Test with Real Market Data

First, verify your market data connection:

```python
# Test in Python
from alpha_bench.data.loader import MarketDataLoader
from datetime import datetime, timedelta

loader = MarketDataLoader(provider="coinapi")  # or your chosen provider
end = datetime.utcnow()
start = end - timedelta(hours=24)

data = loader.fetch_ohlcv("BTC/USD", start, end)
print(f"Fetched {len(data)} rows")
print(data.head())
```

If this works, run a full benchmark:

```bash
python scripts/run_benchmark.py \
    --model claude-code-numeric \
    --lookback 72h \
    --forecast 24h \
    --symbol BTC/USD
```

### Option C: Run Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=alpha_bench --cov-report=html

# View coverage report
open htmlcov/index.html  # macOS
# or
start htmlcov/index.html  # Windows
```

---

## 5. Launch the Dashboard

```bash
streamlit run alpha_bench/dashboard/app.py
```

Then open your browser to: http://localhost:8501

**Note:** You need to run at least one benchmark first to see data in the dashboard.

---

## 6. Set Up Airflow (Optional - For Automated Recurring Runs)

### Step 1: Initialize Airflow

```bash
# Set environment variables
export AIRFLOW_HOME=/c/dev/alpha-bench/airflow_home
export AIRFLOW__CORE__DAGS_FOLDER=/c/dev/alpha-bench/alpha_bench/airflow_dags

# Initialize database
airflow db init

# Create admin user
airflow users create \
    --username admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com \
    --password admin
```

### Step 2: Start Airflow Services

```bash
# Terminal 1: Start scheduler
airflow scheduler

# Terminal 2: Start webserver
airflow webserver --port 8080
```

### Step 3: Access Airflow UI

Open browser to: http://localhost:8080

- Username: `admin`
- Password: `admin`

### Step 4: Enable DAGs

1. Find `benchmark_pipeline` in the DAGs list
2. Toggle it to "On"
3. It will now run every 6 hours automatically

---

## 7. What to Provide for Real Implementation

Here's exactly what you need to run this system for real:

### **Must Have:**

1. **Anthropic API Key**
   - Get it from: https://console.anthropic.com/
   - Add to `.env` as `ANTHROPIC_API_KEY`
   - You'll need credits ($5-10 is enough for testing)

2. **Market Data API Key** (choose ONE):
   - **CoinAPI** (recommended for crypto): https://www.coinapi.io/
   - **Alpha Vantage** (good for stocks): https://www.alphavantage.co/
   - **Yahoo Finance** (free, no key): just install yfinance

3. **Configured .env file** with above keys

### **Optional But Recommended:**

4. **Airflow setup** (if you want automated recurring runs)
   - Requires PostgreSQL for production (SQLite is fine for testing)
   - Requires scheduler running in background

5. **Local LLM models** (if using llama.cpp provider)
   - Download GGUF model file (4-7GB)
   - Update `model_path` in `configs/models.yaml`

### **Test Before Going Live:**

```bash
# 1. Test with mock data first (no cost)
python scripts/run_benchmark.py --model baseline-random

# 2. Test market data connection
python -c "from alpha_bench.data.loader import MarketDataLoader; \
           from datetime import datetime, timedelta; \
           loader = MarketDataLoader(provider='mock'); \
           data = loader.fetch_latest('BTC/USD', lookback_hours=24); \
           print(f'Success: {len(data)} rows fetched')"

# 3. Test with one Claude API call (will cost ~$0.01)
python scripts/run_benchmark.py \
    --model claude-code-numeric \
    --lookback 24h \
    --symbol BTC/USD

# 4. If all above work, enable automated runs
# Start Airflow and enable benchmark_pipeline DAG
```

---

## 8. Costs & Limits

### Estimated Costs (per run):

- **Anthropic Claude API**: $0.01 - $0.05 per run (varies by data size)
- **Market Data**:
  - CoinAPI Free: 100 requests/day (enough for ~10 runs)
  - Alpha Vantage Free: 500 requests/day
  - Yahoo Finance: Free (unlimited)

### Recommended Starting Configuration:

- **For Testing**: Mock data + baseline models (FREE)
- **For Light Production**: Yahoo Finance + Claude API (~$2-5/month)
- **For Serious Use**: CoinAPI paid tier + Claude API (~$20-50/month)

---

## 9. Troubleshooting

### "ModuleNotFoundError: No module named 'alpha_bench'"

```bash
# Ensure you're in the project directory
cd /c/dev/alpha-bench

# Activate virtual environment
source venv/bin/activate

# Reinstall in development mode
pip install -e .
```

### "API key not found" errors

```bash
# Verify .env file exists and has correct values
cat .env | grep API_KEY

# Ensure .env is being loaded
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('ANTHROPIC_API_KEY'))"
```

### "No benchmark data available" in dashboard

```bash
# Run at least one benchmark first
python scripts/run_benchmark.py --model baseline-random --lookback 72h

# Check results directory
ls -la results/
```

### Airflow DAGs not appearing

```bash
# Verify DAGs folder is set correctly
echo $AIRFLOW__CORE__DAGS_FOLDER

# Check for syntax errors in DAG files
airflow dags list

# If needed, refresh Airflow
airflow db reset  # Warning: This clears all history!
```

---

## 10. Next Steps

Once setup is complete:

1. **Run your first benchmark** with real data
2. **View results** in the dashboard
3. **Enable Airflow** for automated recurring runs
4. **Add custom models** in `configs/models.yaml`
5. **Experiment with different strategies**
6. **Analyze results** over time

For more information, see:
- [README.md](README.md) - Project overview
- [CLAUDE.md](CLAUDE.md) - Development guide
- [QUICKSTART.md](QUICKSTART.md) - 5-minute quickstart

---

## Support

If you encounter issues:

1. Check the troubleshooting section above
2. Review logs in `logs/alpha_bench.log`
3. Enable debug mode: `LOG_LEVEL=DEBUG` in `.env`
4. Open an issue on GitHub with error details

Happy benchmarking! 🚀
