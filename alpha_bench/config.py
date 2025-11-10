"""Configuration management for alpha-bench.

This module handles loading configuration from:
1. YAML files (configs/models.yaml, configs/strategies.yaml)
2. Environment variables (.env)
3. Default values

Usage:
    from alpha_bench.config import Config

    config = Config.load()
    models = config.get_models()
    strategies = config.get_strategies()
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv


@dataclass
class ModelConfig:
    """Configuration for a single LLM model."""

    id: str
    description: str
    provider: str
    system_prompt: str
    features: List[str]
    schedule: str
    risk_cap: float
    enabled: bool = True

    # Provider-specific fields
    model_name: Optional[str] = None
    model_path: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = 0.2
    n_ctx: Optional[int] = None
    n_threads: Optional[int] = None
    strategy: Optional[str] = None

    def __post_init__(self):
        """Validate model configuration."""
        if self.risk_cap <= 0 or self.risk_cap > 1:
            raise ValueError(f"risk_cap must be in (0, 1], got {self.risk_cap}")


@dataclass
class StrategyConfig:
    """Configuration for trading strategies."""

    position_sizing: Dict[str, Any] = field(default_factory=dict)
    risk_management: Dict[str, Any] = field(default_factory=dict)
    execution: Dict[str, Any] = field(default_factory=dict)
    strategies: Dict[str, Any] = field(default_factory=dict)
    baseline_strategies: Dict[str, Any] = field(default_factory=dict)
    backtesting: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    alerts: Dict[str, Any] = field(default_factory=dict)


class Config:
    """Main configuration manager for alpha-bench."""

    def __init__(
        self,
        project_root: Optional[Path] = None,
        env_file: Optional[str] = ".env",
    ):
        """Initialize configuration manager.

        Args:
            project_root: Root directory of the project. If None, auto-detect.
            env_file: Name of environment file to load. Default is .env.
        """
        self.project_root = project_root or self._find_project_root()
        self.configs_dir = self.project_root / "configs"
        self.prompts_dir = self.project_root / "prompts"

        # Load environment variables
        env_path = self.project_root / env_file
        if env_path.exists():
            load_dotenv(env_path)

        # Load YAML configs
        self._models_config: Optional[Dict] = None
        self._strategies_config: Optional[Dict] = None

    @staticmethod
    def _find_project_root() -> Path:
        """Auto-detect project root by looking for CLAUDE.md or setup.py."""
        current = Path.cwd()

        # Look for marker files
        markers = ["CLAUDE.md", "setup.py", "alpha_bench"]

        for parent in [current, *current.parents]:
            if any((parent / marker).exists() for marker in markers):
                return parent

        # Fallback to current directory
        return current

    def _load_yaml(self, filename: str) -> Dict:
        """Load YAML configuration file.

        Args:
            filename: Name of YAML file in configs/ directory.

        Returns:
            Parsed YAML content as dictionary.

        Raises:
            FileNotFoundError: If config file doesn't exist.
            yaml.YAMLError: If file is not valid YAML.
        """
        filepath = self.configs_dir / filename

        if not filepath.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {filepath}\n"
                f"Expected location: {filepath.absolute()}"
            )

        with open(filepath, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def get_models_config(self) -> Dict:
        """Get raw models configuration dictionary.

        Returns:
            Models configuration dictionary from models.yaml.
        """
        if self._models_config is None:
            self._models_config = self._load_yaml("models.yaml")
        return self._models_config

    def get_strategies_config(self) -> Dict:
        """Get raw strategies configuration dictionary.

        Returns:
            Strategies configuration dictionary from strategies.yaml.
        """
        if self._strategies_config is None:
            self._strategies_config = self._load_yaml("strategies.yaml")
        return self._strategies_config

    def get_models(self, enabled_only: bool = True) -> List[ModelConfig]:
        """Get list of model configurations.

        Args:
            enabled_only: If True, return only enabled models. Default True.

        Returns:
            List of ModelConfig objects.
        """
        config = self.get_models_config()
        models = []

        for model_data in config.get("models", []):
            model = ModelConfig(**model_data)
            if not enabled_only or model.enabled:
                models.append(model)

        return models

    def get_model(self, model_id: str) -> Optional[ModelConfig]:
        """Get configuration for a specific model by ID.

        Args:
            model_id: Model identifier.

        Returns:
            ModelConfig if found, None otherwise.
        """
        for model in self.get_models(enabled_only=False):
            if model.id == model_id:
                return model
        return None

    def get_strategies(self) -> StrategyConfig:
        """Get trading strategies configuration.

        Returns:
            StrategyConfig object.
        """
        config = self.get_strategies_config()
        return StrategyConfig(
            position_sizing=config.get("position_sizing", {}),
            risk_management=config.get("risk_management", {}),
            execution=config.get("execution", {}),
            strategies=config.get("strategies", {}),
            baseline_strategies=config.get("baseline_strategies", {}),
            backtesting=config.get("backtesting", {}),
            metrics=config.get("metrics", {}),
            alerts=config.get("alerts", {}),
        )

    def get_feature_config(self) -> Dict[str, Any]:
        """Get feature engineering configuration.

        Returns:
            Feature configuration dictionary.
        """
        config = self.get_models_config()
        return config.get("feature_config", {})

    def get_provider_defaults(self, provider: str) -> Dict[str, Any]:
        """Get default settings for a model provider.

        Args:
            provider: Provider name (e.g., 'claude_code', 'llama_cpp').

        Returns:
            Provider defaults dictionary.
        """
        config = self.get_models_config()
        defaults = config.get("provider_defaults", {})
        return defaults.get(provider, {})

    def get_system_prompt(self, filename: str) -> str:
        """Load system prompt from prompts/ directory.

        Args:
            filename: Name of prompt file.

        Returns:
            Prompt text content.

        Raises:
            FileNotFoundError: If prompt file doesn't exist.
        """
        filepath = self.prompts_dir / filename

        if not filepath.exists():
            raise FileNotFoundError(
                f"Prompt file not found: {filepath}\n"
                f"Expected location: {filepath.absolute()}"
            )

        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value from environment or defaults.

        Args:
            key: Configuration key (environment variable name).
            default: Default value if key not found.

        Returns:
            Configuration value.

        Examples:
            >>> config = Config.load()
            >>> api_key = config.get('ANTHROPIC_API_KEY')
            >>> lookback = config.get('DEFAULT_LOOKBACK_HOURS', 72)
        """
        return os.getenv(key, default)

    def get_int(self, key: str, default: int = 0) -> int:
        """Get integer configuration value.

        Args:
            key: Configuration key.
            default: Default value if key not found or invalid.

        Returns:
            Integer value.
        """
        try:
            return int(os.getenv(key, default))
        except (ValueError, TypeError):
            return default

    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get float configuration value.

        Args:
            key: Configuration key.
            default: Default value if key not found or invalid.

        Returns:
            Float value.
        """
        try:
            return float(os.getenv(key, default))
        except (ValueError, TypeError):
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean configuration value.

        Args:
            key: Configuration key.
            default: Default value if key not found.

        Returns:
            Boolean value.
        """
        value = os.getenv(key)
        if value is None:
            return default
        return value.lower() in ("true", "1", "yes", "on")

    @classmethod
    def load(cls, **kwargs) -> "Config":
        """Load configuration with default settings.

        Args:
            **kwargs: Arguments passed to Config constructor.

        Returns:
            Configured Config instance.
        """
        return cls(**kwargs)

    def validate(self) -> List[str]:
        """Validate configuration and return list of errors.

        Returns:
            List of error messages (empty if valid).
        """
        errors = []

        # Check required environment variables
        required_vars = [
            "ANTHROPIC_API_KEY",
            "MARKET_DATA_API_KEY",
        ]

        for var in required_vars:
            if not os.getenv(var):
                errors.append(f"Missing required environment variable: {var}")

        # Check config files exist
        if not self.configs_dir.exists():
            errors.append(f"Configs directory not found: {self.configs_dir}")

        if not self.prompts_dir.exists():
            errors.append(f"Prompts directory not found: {self.prompts_dir}")

        # Validate models config
        try:
            models = self.get_models()
            if not models:
                errors.append("No enabled models found in models.yaml")

            # Check system prompts exist
            for model in models:
                prompt_path = self.prompts_dir / model.system_prompt
                if not prompt_path.exists():
                    errors.append(
                        f"System prompt not found for model {model.id}: {prompt_path}"
                    )
        except Exception as e:
            errors.append(f"Error loading models config: {e}")

        # Validate strategies config
        try:
            self.get_strategies()
        except Exception as e:
            errors.append(f"Error loading strategies config: {e}")

        return errors

    def __repr__(self) -> str:
        """String representation of config."""
        models_count = len(self.get_models(enabled_only=False))
        enabled_count = len(self.get_models(enabled_only=True))
        return (
            f"Config(project_root={self.project_root}, "
            f"models={enabled_count}/{models_count} enabled)"
        )


# Convenience function for quick access
def load_config(**kwargs) -> Config:
    """Load configuration (convenience function).

    Args:
        **kwargs: Arguments passed to Config.load().

    Returns:
        Configured Config instance.
    """
    return Config.load(**kwargs)
