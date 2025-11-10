---
description: "Add a new feature using TDD workflow"
---

# Add New Feature (Test-Driven Development)

Implement a new feature for alpha-bench using Test-Driven Development methodology.

## Usage

```
/feature <feature_name>
```

## TDD Workflow

### 1. Write Tests First (RED)

Create test file in `tests/` directory matching the module you're adding to:

```python
# Example: tests/test_data/test_new_indicator.py

import pytest
import pandas as pd
from alpha_bench.data.features import FeatureEngineer

def test_new_indicator_calculation():
    """Test that new indicator is calculated correctly."""
    # Arrange
    engineer = FeatureEngineer()
    mock_data = pd.DataFrame({
        'close': [100, 102, 101, 103, 105],
    })

    # Act
    result = engineer.calculate_new_indicator(mock_data)

    # Assert
    assert 'new_indicator' in result.columns
    assert len(result) == len(mock_data)
    assert result['new_indicator'].iloc[-1] == pytest.approx(expected_value)

def test_new_indicator_edge_cases():
    """Test edge cases for new indicator."""
    engineer = FeatureEngineer()

    # Test with insufficient data
    small_data = pd.DataFrame({'close': [100]})
    with pytest.raises(ValueError):
        engineer.calculate_new_indicator(small_data)

    # Test with NaN values
    nan_data = pd.DataFrame({'close': [100, None, 102]})
    result = engineer.calculate_new_indicator(nan_data)
    assert result is not None
```

Run tests (they should FAIL):
```bash
pytest tests/test_data/test_new_indicator.py -v
```

### 2. Implement Feature (GREEN)

Implement the minimum code to make tests pass:

```python
# Example: alpha_bench/data/features.py

class FeatureEngineer:
    # ... existing code ...

    def calculate_new_indicator(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate new custom indicator.

        Args:
            data: DataFrame with OHLCV data

        Returns:
            DataFrame with new_indicator column added

        Raises:
            ValueError: If insufficient data points
        """
        if len(data) < 2:
            raise ValueError("Need at least 2 data points")

        result = data.copy()

        # Handle NaN values
        clean_data = data['close'].fillna(method='ffill')

        # Calculate indicator
        result['new_indicator'] = clean_data.rolling(window=2).mean()

        return result
```

Run tests (they should PASS):
```bash
pytest tests/test_data/test_new_indicator.py -v
```

### 3. Refactor (REFACTOR)

Improve code quality while keeping tests green:

- Extract helper functions
- Add type hints
- Improve error messages
- Add docstrings
- Optimize performance

Run tests again to ensure refactoring didn't break anything:
```bash
pytest tests/test_data/test_new_indicator.py -v
```

### 4. Integration Testing

Add integration test to ensure feature works in full pipeline:

```python
# tests/test_integration/test_pipeline.py

def test_new_indicator_in_pipeline():
    """Test new indicator integrates with full pipeline."""
    from alpha_bench.data.loader import MarketDataLoader
    from alpha_bench.data.features import FeatureEngineer

    loader = MarketDataLoader()
    data = loader.load_sample_data()

    engineer = FeatureEngineer()
    features = engineer.generate_all_features(data)

    assert 'new_indicator' in features.columns
```

### 5. Update Configuration

Add feature to model configs:

```yaml
# configs/models.yaml

models:
  - id: claude-code-with-new-indicator
    provider: claude_code
    features:
      - price
      - ema_12
      - new_indicator  # ← Add here
    # ... rest of config
```

### 6. Code Quality Checks

Run full quality check suite:

```bash
# Format code
black . && isort .

# Lint
flake8 .

# Type check
mypy alpha_bench/

# Full test suite
pytest --cov=alpha_bench
```

### 7. Documentation

Update relevant documentation:

- Add docstring to function
- Update `CLAUDE.md` if it's a significant feature
- Add example to `docs/api.md`

### 8. Commit

Commit with descriptive message:

```bash
git add .
git commit -m "Add new_indicator feature with full test coverage

- Implemented calculate_new_indicator() in FeatureEngineer
- Added comprehensive unit tests (100% coverage)
- Added integration test with full pipeline
- Updated model configs to support new feature
- All quality checks passing

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

## Checklist

- [ ] Write failing tests (RED)
- [ ] Implement minimal code to pass tests (GREEN)
- [ ] Refactor for quality (REFACTOR)
- [ ] Add integration tests
- [ ] Update configuration files
- [ ] Run code quality checks (black, flake8, mypy)
- [ ] Update documentation
- [ ] Commit changes

## Tips

- **Start with tests** - Don't write implementation first
- **Small iterations** - Get to green quickly, refactor later
- **Test edge cases** - Empty data, NaN, extreme values
- **Keep tests fast** - Use mocks for external dependencies
- **Maintain coverage** - Aim for 80%+ overall, 100% for critical paths
