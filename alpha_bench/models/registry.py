"""Model registry for alpha-bench.

This module handles loading and instantiating trading models from configuration files.
It serves as a factory for creating model instances based on their type.

Usage:
    from alpha_bench.models.registry import ModelRegistry

    registry = ModelRegistry()
    model = registry.load_model('claude-code-numeric')
"""

import logging
from typing import Dict, List, Optional

from alpha_bench.config import Config, ModelConfig
from alpha_bench.models.base import BaseTradingModel, BaselineModel, TradingDecision

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Registry for loading and managing trading models.

    Attributes:
        config: Config instance
        loaded_models: Cache of loaded model instances
    """

    def __init__(self, config: Optional[Config] = None):
        """Initialize model registry.

        Args:
            config: Config instance (creates new one if None)
        """
        self.config = config or Config.load()
        self.loaded_models: Dict[str, BaseTradingModel] = {}

    def load_model(self, model_id: str) -> BaseTradingModel:
        """Load a trading model by ID.

        Args:
            model_id: Model identifier from config.yaml

        Returns:
            Instantiated trading model

        Raises:
            ValueError: If model ID not found or model type unsupported
        """
        # Check cache
        if model_id in self.loaded_models:
            logger.debug(f"Returning cached model: {model_id}")
            return self.loaded_models[model_id]

        # Get model config
        model_config = self.config.get_model(model_id)
        if model_config is None:
            raise ValueError(f"Model not found in config: {model_id}")

        # Load model based on provider
        provider = model_config.provider
        logger.info(f"Loading model {model_id} (provider: {provider})")

        if provider == "claude_code":
            model = self._load_claude_code_model(model_config)
        elif provider == "llama_cpp":
            model = self._load_llama_cpp_model(model_config)
        elif provider == "baseline":
            model = self._load_baseline_model(model_config)
        else:
            raise ValueError(f"Unsupported model provider: {provider}")

        # Cache and return
        self.loaded_models[model_id] = model
        return model

    def load_all_enabled(self) -> Dict[str, BaseTradingModel]:
        """Load all enabled models from config.

        Returns:
            Dictionary mapping model_id to model instance
        """
        models = {}
        for model_config in self.config.get_models(enabled_only=True):
            try:
                model = self.load_model(model_config.id)
                models[model_config.id] = model
            except Exception as e:
                logger.error(f"Failed to load model {model_config.id}: {e}")

        logger.info(f"Loaded {len(models)} enabled models")
        return models

    def list_models(self, enabled_only: bool = True) -> List[str]:
        """List all available model IDs.

        Args:
            enabled_only: If True, only return enabled models

        Returns:
            List of model IDs
        """
        models = self.config.get_models(enabled_only=enabled_only)
        return [m.id for m in models]

    def get_model_info(self, model_id: str) -> Dict:
        """Get information about a model.

        Args:
            model_id: Model identifier

        Returns:
            Dictionary with model information
        """
        model_config = self.config.get_model(model_id)
        if model_config is None:
            raise ValueError(f"Model not found: {model_id}")

        return {
            "id": model_config.id,
            "description": model_config.description,
            "provider": model_config.provider,
            "features": model_config.features,
            "enabled": model_config.enabled,
            "schedule": model_config.schedule,
            "risk_cap": model_config.risk_cap,
        }

    def _load_claude_code_model(self, config: ModelConfig) -> BaseTradingModel:
        """Load Claude Code API model.

        Args:
            config: Model configuration

        Returns:
            ClaudeCodeModel instance
        """
        from alpha_bench.models.claude_code import ClaudeCodeModel

        # Load system prompt
        system_prompt = self.config.get_system_prompt(config.system_prompt)

        # Create model instance
        model = ClaudeCodeModel(
            model_id=config.id,
            config=config.__dict__,
            system_prompt=system_prompt,
        )

        return model

    def _load_llama_cpp_model(self, config: ModelConfig) -> BaseTradingModel:
        """Load llama.cpp local model.

        Args:
            config: Model configuration

        Returns:
            LlamaCppModel instance
        """
        # Import here to avoid requiring llama-cpp-python if not used
        try:
            from alpha_bench.models.llama_cpp import LlamaCppModel
        except ImportError:
            raise ImportError(
                "llama-cpp-python required for llama_cpp provider. "
                "Install with: pip install llama-cpp-python"
            )

        # Load system prompt
        system_prompt = self.config.get_system_prompt(config.system_prompt)

        # Create model instance
        model = LlamaCppModel(
            model_id=config.id,
            config=config.__dict__,
            system_prompt=system_prompt,
        )

        return model

    def _load_baseline_model(self, config: ModelConfig) -> BaseTradingModel:
        """Load baseline model (random, trend-following, etc.).

        Args:
            config: Model configuration

        Returns:
            Baseline model instance
        """
        from alpha_bench.models.baseline import (
            RandomBaselineModel,
            TrendFollowingModel,
        )

        strategy = config.strategy
        logger.info(f"Loading baseline model with strategy: {strategy}")

        if strategy == "random":
            return RandomBaselineModel(config.id, config.__dict__)
        elif strategy == "ema_crossover" or strategy == "trend_following":
            return TrendFollowingModel(config.id, config.__dict__)
        else:
            raise ValueError(f"Unknown baseline strategy: {strategy}")

    def clear_cache(self):
        """Clear cached model instances."""
        self.loaded_models.clear()
        logger.debug("Cleared model cache")

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"ModelRegistry(loaded={len(self.loaded_models)}, "
            f"available={len(self.list_models())})"
        )


# Convenience functions
def load_model(model_id: str, config: Optional[Config] = None) -> BaseTradingModel:
    """Load a model by ID (convenience function).

    Args:
        model_id: Model identifier
        config: Optional Config instance

    Returns:
        Instantiated trading model
    """
    registry = ModelRegistry(config)
    return registry.load_model(model_id)


def list_available_models(
    enabled_only: bool = True, config: Optional[Config] = None
) -> List[str]:
    """List available model IDs (convenience function).

    Args:
        enabled_only: If True, only return enabled models
        config: Optional Config instance

    Returns:
        List of model IDs
    """
    registry = ModelRegistry(config)
    return registry.list_models(enabled_only=enabled_only)
