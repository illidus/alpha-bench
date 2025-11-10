# CLAUDE.md

## Project Overview

alpha-bench is an automated recurring simulation framework for evaluating LLM-based trading strategies. The system runs controlled trading simulations on a fixed schedule using up-to-date market and sentiment data to generate longitudinal performance logs, build training datasets, and maintain cross-time comparability between model versions.

This is a paper trading benchmark harness only - no live order execution.

## Quick Start Commands

### Environment Setup
```bash
cd /c/dev/alpha-bench
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Configuration
```bash
# Copy environment template and configure
cp .env.example .env
# Edit .env with your API keys and settings
```

### Running Benchmarks
```bash
# Manual single benchmark run
python scripts/run_benchmark.py --model claude-code-numeric --lookback 72h --forecast 24h

# Start Airflow scheduler (for automated runs)
airflow db init
airflow scheduler &
airflow webserver &
# Access UI at http://localhost:8080

# Trigger benchmark DAG manually
airflow dags trigger benchmark_pipeline

# List all runs
python -c "import pandas as pd; print(pd.read_parquet('results/benchmarks.parquet'))"
```

### Dashboard
```bash
# Launch Streamlit dashboard
streamlit run alpha_bench/dashboard/app.py
# Access at http://localhost:8501
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=alpha_bench --cov-report=html --cov-report=term

# Run specific test module
pytest tests/test_simulation/test_engine.py -v

# Run tests matching pattern
pytest -k "test_risk" -v
```

### Code Quality
```bash
# Format code
black . && isort .

# Check formatting without changes
black --check . && isort --check-only .

# Linting
flake8 .

# Type checking
mypy alpha_bench/

# Run all quality checks
black . && isort . && flake8 . && mypy alpha_bench/ && pytest
```

### Data Operations
```bash
# Fetch latest market data (manual)
python -c "from alpha_bench.data.loader import MarketDataLoader; loader = MarketDataLoader(); loader.fetch_latest()"

# Generate features from cached data
python -c "from alpha_bench.data.features import FeatureEngineer; eng = FeatureEngineer(); eng.generate_features('2025-11-10')"

# Archive old data (>90 days)
python scripts/archive_data.py --older-than 90
```

### Git Operations
```bash
git status
git add .
git commit  # Let Claude write descriptive commit messages
git log --oneline -10
git diff HEAD~1
```

## Project Structure

```
alpha-bench/
├── alpha_bench/              # Main package
│   ├── config.py            # Configuration management (YAML, env vars)
│   ├── data/                # Market data ingestion & feature engineering
│   │   ├── loader.py        # API integration for OHLCV data
│   │   ├── features.py      # Technical indicators + text features
│   │   └── cache.py         # Local data caching
│   ├── models/              # LLM model interfaces
│   │   ├── base.py          # Abstract BaseTradingModel interface
│   │   ├── claude_code.py   # Claude Code API integration
│   │   ├── llama_cpp.py     # Local llama.cpp inference
│   │   └── registry.py      # Model loading from configs/models.yaml
│   ├── simulation/          # Paper trading engine
│   │   ├── engine.py        # Core simulation loop (portfolio tracking)
│   │   ├── executor.py      # Order execution (fees, slippage modeling)
│   │   └── risk.py          # Risk management rules
│   ├── metrics/             # Performance evaluation
│   │   ├── calculator.py    # PnL, Sharpe, Sortino, max drawdown, etc.
│   │   └── aggregator.py    # Rolling metrics & benchmarks.parquet
│   ├── airflow_dags/        # Orchestration workflows
│   │   ├── benchmark_dag.py # Main 6-hour recurring pipeline
│   │   └── maintenance_dag.py # Data cleanup & archival
│   └── dashboard/           # Streamlit visualization
│       ├── app.py           # Multi-page Streamlit app
│       ├── components/      # Reusable UI components
│       └── queries.py       # Data loading for dashboard
├── configs/                  # YAML configuration files
│   ├── models.yaml          # Model registry (per RFC-001-A)
│   └── strategies.yaml      # Trading strategy configs
├── prompts/                  # System prompts for LLMs
│   ├── sys_numeric.txt      # Prompt for numeric features only
│   ├── sys_text.txt         # Prompt with text + numeric features
│   └── sys_base.txt         # Base trading prompt template
├── data/                     # Local data storage
│   ├── runs/{date}/         # Per-run data (market.parquet, features.parquet)
│   └── cache/               # Cached market data
├── results/                  # Benchmark outputs
│   ├── {run_id}/{model_id}/ # Per-model results (decisions, sim_results, metrics)
│   └── benchmarks.parquet   # Aggregated long-term results
├── tests/                    # Test suite (mirrors alpha_bench/ structure)
└── scripts/                  # Utility scripts
```

## Development Workflow

### Adding a New Feature (TDD Approach)
1. **Write tests first** in `tests/test_<module>/test_<feature>.py`
2. **Run tests** - they should fail (red)
3. **Implement feature** in `alpha_bench/<module>/<file>.py`
4. **Run tests again** - they should pass (green)
5. **Refactor** if needed while keeping tests green
6. **Run code quality checks** (black, flake8, mypy)
7. **Commit** with descriptive message

### Adding a New LLM Model
1. **Create model config** in `configs/models.yaml`:
   ```yaml
   - id: my-new-model
     provider: claude_code  # or llama_cpp
     system_prompt: sys_custom.txt
     features: [price, ema, rsi]
     schedule: 6h
     risk_cap: 0.01
   ```
2. **Create system prompt** in `prompts/sys_custom.txt`
3. **Test model loading**:
   ```python
   from alpha_bench.models.registry import load_model
   model = load_model("my-new-model")
   ```
4. **Run test simulation**: `python scripts/run_benchmark.py --model my-new-model`
5. **Add to Airflow DAG** - model will be picked up automatically from YAML
6. **Monitor first few runs** in dashboard

### Debugging a Failed Simulation
1. **Check Airflow logs**: UI → DAGs → benchmark_pipeline → Task Instance → Logs
2. **Inspect run data**: `results/{run_id}/{model_id}/decisions.parquet`
3. **Reproduce locally**:
   ```python
   from alpha_bench.simulation.engine import SimulationEngine
   engine = SimulationEngine.from_run_id("2025-11-10T12:00Z", "model-id")
   engine.replay()  # Step through with debugger
   ```
4. **Check model response**: Look at `rationale` column in decisions.parquet
5. **Fix issue** and re-run: `airflow dags trigger benchmark_pipeline`

### Modifying Airflow DAG
1. **Edit** `alpha_bench/airflow_dags/benchmark_dag.py`
2. **Validate DAG**: `airflow dags list` (should appear without errors)
3. **Test DAG**: `airflow dags test benchmark_pipeline $(date +%Y-%m-%d)`
4. **Monitor execution**: Airflow UI → DAGs → benchmark_pipeline → Graph
5. **Note**: DAG changes are picked up automatically by scheduler

## Style Guidelines

### Python Code Style
- **PEP 8 compliant** (enforced by black + flake8)
- **Max line length**: 100 characters
- **Formatting**: Use `black` and `isort` (Black-compatible profile)
- **Type hints**: Required for all function signatures
  ```python
  def calculate_sharpe(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
      ...
  ```
- **Docstrings**: Google-style for all public functions/classes
  ```python
  def fetch_market_data(symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
      """Fetch OHLCV market data for a symbol.

      Args:
          symbol: Trading symbol (e.g., 'BTC/USD')
          start: Start datetime (inclusive)
          end: End datetime (exclusive)

      Returns:
          DataFrame with columns: open, high, low, close, volume

      Raises:
          APIError: If data source is unavailable
          ValueError: If date range is invalid
      """
  ```

### Naming Conventions
- **Classes**: PascalCase (`MarketDataLoader`, `SimulationEngine`)
- **Functions/methods**: snake_case (`fetch_market_data`, `calculate_metrics`)
- **Constants**: UPPER_SNAKE_CASE (`DEFAULT_LOOKBACK_HOURS`, `MAX_POSITION_SIZE`)
- **Private members**: Leading underscore (`_format_prompt`, `_cache_key`)

### Code Organization
- **Imports**: Grouped as stdlib, third-party, local (isort handles this)
- **Class order**: Public methods first, private methods last
- **Function length**: Keep under 50 lines; extract helpers if longer
- **Cyclomatic complexity**: Max 10 per function (flake8 will warn)

### Comments Philosophy
- **Avoid obvious comments**: Code should be self-documenting
- **Explain "why" not "what"**: Focus on non-obvious decisions
  ```python
  # Good: Explain business logic
  # Use 72-hour lookback to capture full weekend price action
  lookback_hours = 72

  # Bad: State the obvious
  # Set lookback hours to 72
  lookback_hours = 72
  ```
- **TODO comments**: Include issue number
  ```python
  # TODO(#42): Add support for multiple timeframes
  ```

## Testing Strategy

### Test Structure
```
tests/
├── conftest.py               # Shared fixtures
├── test_data/
│   ├── test_loader.py       # API mocking
│   └── test_features.py     # Feature generation
├── test_models/
│   ├── test_claude_code.py  # LLM integration
│   └── test_registry.py     # Model loading
├── test_simulation/
│   ├── test_engine.py       # Core simulation logic
│   ├── test_executor.py     # Order execution
│   └── test_risk.py         # Risk management
└── test_metrics/
    ├── test_calculator.py   # Metric computation
    └── test_aggregator.py   # Result aggregation
```

### Testing Principles
- **Arrange-Act-Assert** pattern in all tests
- **Mock external dependencies** (API calls, LLM responses)
- **Parametrize** tests for multiple input scenarios
- **Fixtures** for common test data (market data, mock responses)

### Coverage Goals
- **Overall**: 80%+ coverage
- **Critical paths**: 100% coverage
  - `simulation/engine.py` (portfolio tracking)
  - `simulation/risk.py` (risk management)
  - `metrics/calculator.py` (performance metrics)

### Example Fixtures (conftest.py)
```python
import pytest
import pandas as pd

@pytest.fixture
def mock_market_data():
    """Generate realistic OHLCV data for testing."""
    dates = pd.date_range('2025-11-01', periods=100, freq='1h')
    return pd.DataFrame({
        'open': 50000 + np.random.randn(100) * 100,
        'high': 50100 + np.random.randn(100) * 100,
        'low': 49900 + np.random.randn(100) * 100,
        'close': 50000 + np.random.randn(100) * 100,
        'volume': 1000 + np.random.randn(100) * 50,
    }, index=dates)

@pytest.fixture
def mock_llm_response():
    """Mock LLM decision response."""
    return {
        'action': 'buy',
        'symbol': 'BTC/USD',
        'size': 0.1,
        'confidence': 0.75,
        'rationale': 'RSI oversold, MACD bullish crossover'
    }
```

## Common Patterns

### Configuration Management
```python
# Load from YAML + environment variables
from alpha_bench.config import Config

config = Config.load()
api_key = config.get('market_data_api_key')  # From .env
models = config.get_models()  # From configs/models.yaml
```

### Error Handling
- **Use custom exceptions** for domain errors
  ```python
  class SimulationError(Exception):
      """Raised when simulation encounters an error."""

  class RiskLimitExceeded(SimulationError):
      """Raised when risk limits are breached."""
  ```
- **Fail fast** on configuration errors (startup)
- **Retry with backoff** for transient API errors
  ```python
  from tenacity import retry, stop_after_attempt, wait_exponential

  @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
  def fetch_market_data(symbol: str) -> pd.DataFrame:
      ...
  ```
- **Log errors** but don't crash the DAG
  ```python
  try:
      result = simulate_model(model_id)
  except SimulationError as e:
      logger.error(f"Simulation failed for {model_id}: {e}")
      return None  # Allow other models to continue
  ```

### Logging
```python
import logging

logger = logging.getLogger(__name__)

# Standard log levels
logger.debug("Detailed info for debugging")
logger.info("High-level progress updates")
logger.warning("Something unexpected but handled")
logger.error("Error occurred, operation failed")
logger.critical("System-level failure")

# Include context
logger.info(f"Fetching data for {symbol} from {start} to {end}")
```

### Async Operations (Data Fetching)
```python
import asyncio
import aiohttp

async def fetch_multiple_symbols(symbols: list[str]) -> dict[str, pd.DataFrame]:
    """Fetch data for multiple symbols in parallel."""
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_symbol_data(session, symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    return dict(zip(symbols, results))
```

### LLM Rate Limiting
```python
import time
from collections import deque

class RateLimiter:
    """Token bucket rate limiter for LLM API calls."""
    def __init__(self, requests_per_minute: int = 50):
        self.requests_per_minute = requests_per_minute
        self.requests = deque()

    def wait_if_needed(self):
        now = time.time()
        # Remove requests older than 1 minute
        while self.requests and self.requests[0] < now - 60:
            self.requests.popleft()
        # Wait if at limit
        if len(self.requests) >= self.requests_per_minute:
            sleep_time = 60 - (now - self.requests[0])
            time.sleep(sleep_time)
        self.requests.append(time.time())
```

### Data Validation (Pydantic)
```python
from pydantic import BaseModel, Field, validator

class TradingDecision(BaseModel):
    """Structured output from LLM model."""
    action: str  # 'buy', 'sell', 'hold'
    symbol: str
    size: float = Field(gt=0)
    confidence: float = Field(ge=0, le=1)
    rationale: str

    @validator('action')
    def validate_action(cls, v):
        if v not in ['buy', 'sell', 'hold']:
            raise ValueError(f"Invalid action: {v}")
        return v
```

## Dependencies

### Core Dependencies
- **pandas** (2.0+): Data manipulation
- **pyarrow** (12.0+): Parquet file I/O
- **numpy** (1.24+): Numerical operations
- **pydantic** (2.0+): Data validation
- **python-dotenv**: Environment variable management

### LLM Integration
- **anthropic** (0.18+): Claude Code API client
- **llama-cpp-python** (0.2+): Local model inference

### Orchestration
- **apache-airflow** (2.8+): Workflow scheduling
- **apache-airflow-providers-http**: HTTP operators

### Dashboard
- **streamlit** (1.30+): Interactive web app
- **plotly** (5.18+): Interactive charts
- **altair** (5.2+): Declarative visualizations

### Utilities
- **requests** / **aiohttp**: HTTP clients
- **tenacity** (8.2+): Retry logic with exponential backoff

### Development
- **pytest** (7.4+): Testing framework
- **pytest-cov**: Coverage reporting
- **pytest-asyncio**: Async test support
- **pytest-mock**: Mocking utilities
- **black** (23.0+): Code formatter
- **isort** (5.12+): Import sorter
- **flake8** (6.1+): Linter
- **mypy** (1.7+): Static type checker

## Anti-Patterns to Avoid

### DO NOT:
1. **Hardcode API keys or secrets** in code
   - Use environment variables via `.env`
   - Never commit `.env` to git

2. **Make synchronous API calls in loops**
   - Use async/await or parallel processing
   - Batch requests when possible

3. **Ignore LLM rate limits**
   - Implement rate limiting (see Common Patterns)
   - Handle 429 errors with backoff

4. **Trust LLM output without validation**
   - Always validate with Pydantic models
   - Check for valid actions, reasonable position sizes

5. **Skip error handling in DAGs**
   - Wrap task functions in try/except
   - Log errors, don't let one model crash the pipeline

6. **Modify historical data**
   - Data in `results/` is immutable
   - Create new runs instead of overwriting

7. **Run live trades without extensive testing**
   - This is a paper trading system only
   - Never connect to real trading APIs without explicit review

8. **Use `import *`**
   - Explicit imports only

9. **Leave commented-out code**
   - Remove it (git history preserves old code)

10. **Ignore test failures**
    - Fix tests before merging
    - Maintain >80% coverage

## Additional Notes

### Performance Considerations
- **Parquet compression**: Use 'snappy' for balance of speed/size
- **Chunking**: Process data in chunks for memory efficiency
- **Caching**: Cache technical indicators to avoid recomputation
- **Parallel model execution**: Airflow runs models in parallel by default

### Security
- **API keys**: Store in `.env`, never in code or git
- **Input validation**: Validate all external data (API responses, LLM outputs)
- **Rate limiting**: Respect API limits to avoid bans
- **Audit logging**: Log all trading decisions with timestamps and run_ids

### Data Retention (Per RFC-001-A)
- **Raw decisions**: Keep for 90 days, then archive to cold storage
- **Aggregated metrics**: Keep indefinitely in `benchmarks.parquet`
- **Market data**: Cache for 7 days, then rely on APIs

### Airflow Best Practices
- **Idempotency**: Tasks should produce same result if re-run
- **Atomicity**: Each task should be self-contained
- **Retry logic**: Set `retries=3` for network operations
- **Backfill**: Use `catchup=False` to avoid running historical DAGs

### Versioning & Reproducibility
- **Every run stores**: `commit_hash`, `config_version`, prompt files
- **To reproduce**: Checkout commit, use stored data slice + prompts
- **Config changes**: Increment `config_version` in models.yaml

## Resources

### Project Documentation
- `docs/architecture.md`: System architecture and design decisions
- `docs/api.md`: API reference for all modules
- `docs/RFC-001-A.md`: Original RFC specification

### External Documentation
- [Anthropic API Docs](https://docs.anthropic.com/): Claude Code API reference
- [Airflow Documentation](https://airflow.apache.org/docs/): Workflow orchestration
- [Streamlit Docs](https://docs.streamlit.io/): Dashboard development
- [pandas Documentation](https://pandas.pydata.org/docs/): Data manipulation

### Development Resources
- [Python Type Hints](https://docs.python.org/3/library/typing.html): Type annotation guide
- [pytest Documentation](https://docs.pytest.org/): Testing framework
- [Black Code Style](https://black.readthedocs.io/): Formatting rules

### LLM Resources
- [llama.cpp](https://github.com/ggerganov/llama.cpp): Local model inference
- [Claude Prompt Engineering](https://docs.anthropic.com/claude/docs/introduction-to-prompt-design): Best practices

### Trading/Finance References
- [TA-Lib](https://ta-lib.org/): Technical analysis indicators
- [Quantopian Lectures](https://github.com/quantopian/research_public): Quantitative finance fundamentals

---

## Files to Always Check

When starting work, review these files first to understand the system:
1. This file (CLAUDE.md)
2. `configs/models.yaml` - Active model configurations
3. `alpha_bench/airflow_dags/benchmark_dag.py` - Main workflow
4. `results/benchmarks.parquet` - Latest aggregated results
5. `.env` - Environment configuration (API keys, paths)
6. `prompts/sys_*.txt` - System prompts for models

When making changes, ensure these are updated as needed:
1. Tests in `tests/` (TDD: write tests first!)
2. Type hints and docstrings
3. This CLAUDE.md if workflow changes
4. `docs/api.md` if public APIs change

---

**Last Updated**: 2025-11-10
**Maintainers**: alpha-bench/ops, research-agent, data-agent, eval-agent
