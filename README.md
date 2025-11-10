# alpha-bench

**Automated Recurring Simulation Framework for Longitudinal LLM Trading Evaluation**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

---

## What is alpha-bench?

alpha-bench is a **comprehensive benchmark harness** for evaluating Large Language Model (LLM) performance on trading strategy tasks. It runs automated paper trading simulations on a fixed schedule (e.g., every 6 hours) using real market data and sentiment features to:

- **Generate hypothetical performance logs** for each model/configuration over time
- **Build longitudinal datasets** for training, prompt optimization, and feature ablation studies
- **Maintain cross-time comparability** between model versions and configurations
- **Evaluate LLM reasoning** on market analysis, risk assessment, and strategy recommendations

This is a **paper trading system only** - no live order execution.

---

## Why Use alpha-bench?

### For ML Researchers
- Systematic evaluation of LLM capabilities on financial reasoning tasks
- Longitudinal data for studying model drift and consistency
- Reproducible experiments with versioned prompts and configurations
- Feature importance analysis (technical vs. text features)

### For Quantitative Traders
- Test LLM-based trading ideas without risking capital
- Compare multiple models and prompt strategies side-by-side
- Analyze model performance across different market conditions
- Extract insights for hybrid human-AI strategies

### For AI Engineers
- Benchmark Claude Code API, llama.cpp, and other LLM providers
- Optimize prompts and configurations systematically
- Build production-ready ML pipelines with Airflow
- Create interactive dashboards with Streamlit

---

## Getting Started

### Quick Start (5 minutes)
See [QUICKSTART.md](QUICKSTART.md) for the fastest path to running your first benchmark.

### Full Setup (30 minutes)
Follow the comprehensive guide below for complete installation and configuration.

---

## Installation

### Prerequisites
- Python 3.10 or higher
- Git
- Apache Airflow 2.8+ (installed via requirements.txt)
- API keys for:
  - Anthropic Claude API (for Claude Code integration)
  - Market data provider (e.g., Alpha Vantage, Yahoo Finance, etc.)

### Step 1: Clone the Repository
```bash
cd /c/dev
git clone <your-repo-url> alpha-bench  # Or use the existing directory
cd alpha-bench
```

### Step 2: Set Up Python Environment
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Step 3: Configure Environment Variables
```bash
cp .env.example .env
# Edit .env with your API keys
```

Required variables:
```env
ANTHROPIC_API_KEY=your_anthropic_key_here
MARKET_DATA_API_KEY=your_market_data_key_here
MARKET_DATA_BASE_URL=https://api.yourprovider.com
```

### Step 4: Initialize Airflow
```bash
# Set Airflow home and DAGs folder
export AIRFLOW_HOME=$(pwd)/airflow_home
export AIRFLOW__CORE__DAGS_FOLDER=$(pwd)/alpha_bench/airflow_dags

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

### Step 5: Run Your First Benchmark
```bash
# Manual single run
python scripts/run_benchmark.py --model claude-code-numeric --lookback 72h --forecast 24h

# Or start Airflow and trigger the DAG
airflow scheduler &
airflow webserver &
# Visit http://localhost:8080 and trigger "benchmark_pipeline"
```

### Step 6: View Results
```bash
# Launch the dashboard
streamlit run alpha_bench/dashboard/app.py
# Visit http://localhost:8501
```

---

## Repository Structure

```
alpha-bench/
├── alpha_bench/              # Main Python package
│   ├── config.py            # Configuration management
│   ├── data/                # Market data & feature engineering
│   ├── models/              # LLM interfaces (Claude, llama.cpp)
│   ├── simulation/          # Paper trading engine
│   ├── metrics/             # Performance evaluation
│   ├── airflow_dags/        # Workflow orchestration
│   └── dashboard/           # Streamlit visualization
├── configs/                  # YAML configuration files
│   ├── models.yaml          # Model registry
│   └── strategies.yaml      # Trading strategies
├── prompts/                  # LLM system prompts
├── data/                     # Local data storage
├── results/                  # Benchmark outputs
├── tests/                    # Test suite
├── scripts/                  # Utility scripts
├── docs/                     # Documentation
└── .claude/                  # Claude Code customizations
```

See [CLAUDE.md](CLAUDE.md) for detailed architecture and development guidelines.

---

## What's Included

### ✅ Core Features
- [x] Automated recurring benchmarks (Airflow DAGs)
- [x] Claude Code API integration
- [x] Local LLM support (llama.cpp)
- [x] Paper trading simulation with fees & slippage
- [x] Technical indicator generation (EMA, MACD, RSI, etc.)
- [x] Performance metrics (Sharpe, Sortino, Max DD, etc.)
- [x] Streamlit dashboard for visualization
- [x] Parquet-based data storage
- [x] Model registry and versioning

### 📋 Planned Features
- [ ] Text sentiment features (news, social media)
- [ ] Multiple asset support (crypto, stocks, forex)
- [ ] Advanced risk management rules
- [ ] Meta-learning from accumulated results
- [ ] Fine-tuning dataset export
- [ ] Grafana integration
- [ ] Cloud deployment (AWS, GCP)

---

## Usage

### Running Benchmarks

#### Manual Single Run
```bash
python scripts/run_benchmark.py \
    --model claude-code-numeric \
    --lookback 72h \
    --forecast 24h \
    --symbols BTC/USD,ETH/USD
```

#### Automated Recurring Runs (Airflow)
```bash
# Start Airflow services
airflow scheduler &
airflow webserver &

# DAG will run automatically on schedule (every 6 hours)
# Or trigger manually:
airflow dags trigger benchmark_pipeline
```

### Viewing Results

#### Dashboard (Recommended)
```bash
streamlit run alpha_bench/dashboard/app.py
```

#### Command Line
```python
import pandas as pd

# View all benchmarks
df = pd.read_parquet('results/benchmarks.parquet')
print(df.sort_values('sharpe', ascending=False))

# View specific run decisions
decisions = pd.read_parquet('results/2025-11-10T12:00Z/claude-code-numeric/decisions.parquet')
print(decisions[['timestamp', 'action', 'confidence', 'rationale']])
```

### Adding a New Model

1. **Add to `configs/models.yaml`**:
```yaml
- id: my-custom-model
  provider: claude_code  # or llama_cpp
  system_prompt: sys_custom.txt
  features: [price, ema, macd, rsi, volume]
  schedule: 6h
  risk_cap: 0.01
  temperature: 0.2
```

2. **Create system prompt** in `prompts/sys_custom.txt`:
```
You are a quantitative trading assistant. Given market data and technical indicators, recommend a trading action.

[Your custom instructions here]
```

3. **Run test benchmark**:
```bash
python scripts/run_benchmark.py --model my-custom-model
```

4. **Model will be automatically included** in Airflow DAG on next run.

---

## Development

### Running Tests
```bash
# All tests
pytest

# With coverage
pytest --cov=alpha_bench --cov-report=html

# Specific module
pytest tests/test_simulation/ -v
```

### Code Quality
```bash
# Format and lint
black . && isort . && flake8 . && mypy alpha_bench/

# Pre-commit checks (recommended)
black --check . && isort --check-only . && flake8 . && pytest
```

### Development Workflow
See [CLAUDE.md](CLAUDE.md) for detailed development guidelines, including:
- Test-Driven Development (TDD) approach
- Debugging failed simulations
- Adding new features
- Modifying Airflow DAGs
- Common patterns and anti-patterns

---

## Configuration

### Environment Variables (`.env`)
```env
# LLM APIs
ANTHROPIC_API_KEY=your_key_here
CLAUDE_CODE_API_KEY=your_key_here

# Market Data
MARKET_DATA_API_KEY=your_key_here
MARKET_DATA_BASE_URL=https://api.example.com

# Airflow
AIRFLOW_HOME=/path/to/airflow_home
AIRFLOW__CORE__DAGS_FOLDER=/path/to/alpha_bench/airflow_dags

# Benchmark Settings
DEFAULT_LOOKBACK_HOURS=72
DEFAULT_FORECAST_HOURS=24
DEFAULT_RUN_SCHEDULE="0 */6 * * *"  # Every 6 hours
```

### Model Registry (`configs/models.yaml`)
```yaml
models:
  - id: claude-code-numeric
    provider: claude_code
    system_prompt: sys_numeric.txt
    features: [price, ema, macd, rsi, volume]
    schedule: 6h
    risk_cap: 0.01
    max_tokens: 4096
    temperature: 0.2
```

See example configurations in `configs/` directory.

---

## Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - 5-minute setup guide
- **[CLAUDE.md](CLAUDE.md)** - Comprehensive development guide for AI-assisted development
- **[docs/architecture.md](docs/architecture.md)** - System architecture and design decisions
- **[docs/api.md](docs/api.md)** - API reference for all modules
- **[docs/RFC-001-A.md](docs/RFC-001-A.md)** - Original RFC specification

---

## Architecture

### System Overview
```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Airflow   │────▶│ Data Loader  │────▶│  Features   │
│  Scheduler  │     │  (Market API)│     │  Engineer   │
└─────────────┘     └──────────────┘     └─────────────┘
                                                 │
                                                 ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Dashboard  │◀────│   Metrics    │◀────│ Simulation  │
│ (Streamlit) │     │ Aggregator   │     │   Engine    │
└─────────────┘     └──────────────┘     └─────────────┘
                                                 ▲
                                                 │
                                          ┌─────────────┐
                                          │ LLM Models  │
                                          │ (Claude/cpp)│
                                          └─────────────┘
```

### Data Flow
1. **Scheduler** triggers benchmark pipeline (every 6 hours)
2. **Data Loader** fetches latest market data from APIs
3. **Feature Engineer** generates technical indicators
4. **LLM Models** analyze features and generate trading decisions (parallel)
5. **Simulation Engine** executes paper trades with realistic fees/slippage
6. **Metrics Aggregator** calculates performance metrics (Sharpe, DD, etc.)
7. **Dashboard** visualizes results and trends over time

---

## Best Practices

### For Researchers
1. **Version your prompts** - Store prompts in `prompts/` with descriptive names
2. **Track experiments** - Use model `id` to differentiate configurations
3. **Analyze feature importance** - Check correlation between features and PnL
4. **Compare across time** - Use rolling metrics to understand consistency

### For Engineers
1. **Test before deploying** - Run manual benchmarks before adding to DAG
2. **Monitor Airflow logs** - Check for errors in task execution
3. **Set retry policies** - Handle transient API failures gracefully
4. **Respect rate limits** - Use rate limiting for LLM API calls

### For Traders
1. **Start with simple strategies** - Test basic trend-following first
2. **Validate assumptions** - Check if LLM reasoning makes sense
3. **Account for costs** - Fees and slippage matter in simulation
4. **Never trust blindly** - This is paper trading, not investment advice

---

## Troubleshooting

### Common Issues

**Airflow DAG not appearing**:
```bash
# Check DAG folder is set correctly
echo $AIRFLOW__CORE__DAGS_FOLDER
# Should point to /path/to/alpha_bench/airflow_dags

# Check for syntax errors
airflow dags list
```

**Market data API errors**:
- Verify API key in `.env`
- Check rate limits (most free APIs have 5 req/min)
- Ensure network connectivity

**LLM API rate limits**:
- Implement rate limiting (see `CLAUDE.md` > Common Patterns)
- Use `temperature=0.2` for deterministic outputs
- Cache responses for identical inputs

**Out of memory**:
- Process data in chunks (see `pandas.read_csv(chunksize=...)`)
- Use Parquet compression (`compression='snappy'`)
- Limit lookback window (`--lookback 24h` instead of `--lookback 720h`)

---

## Contributing

Contributions are welcome! Please:

1. **Fork the repository**
2. **Create a feature branch** (`git checkout -b feature/my-feature`)
3. **Write tests** for new features (TDD approach)
4. **Ensure code quality** (`black . && flake8 . && pytest`)
5. **Submit a pull request** with clear description

See [CLAUDE.md](CLAUDE.md) for development guidelines.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- **Anthropic** for Claude Code API and AI-assisted development tools
- **Apache Airflow** community for workflow orchestration
- **Streamlit** team for making dashboards easy
- **TA-Lib** for technical analysis indicators
- **llama.cpp** for local LLM inference

---

## Citation

If you use alpha-bench in your research, please cite:

```bibtex
@software{alphabench2025,
  title={alpha-bench: Automated LLM Trading Evaluation Framework},
  author={Your Name},
  year={2025},
  url={https://github.com/yourusername/alpha-bench}
}
```

---

## Contact

For questions, issues, or feedback:
- **Issues**: [GitHub Issues](https://github.com/yourusername/alpha-bench/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/alpha-bench/discussions)
- **Email**: your.email@example.com

---

## Roadmap

### Phase 1 (Current) - Foundation
- [x] Core data pipeline
- [x] Claude Code integration
- [x] Paper trading engine
- [x] Basic metrics and dashboard

### Phase 2 (Next) - Enhancement
- [ ] Text sentiment features
- [ ] Multi-asset support
- [ ] Advanced risk rules
- [ ] Grafana dashboards

### Phase 3 (Future) - Production
- [ ] Cloud deployment
- [ ] Real-time streaming
- [ ] Meta-learning agents
- [ ] Fine-tuning pipeline

---

**Built with ❤️ using Claude Code**
