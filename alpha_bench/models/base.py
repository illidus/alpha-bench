"""Base trading model interface for alpha-bench.

This module defines the abstract base class that all LLM trading models must implement.
It provides a consistent interface for generating trading decisions.

Usage:
    from alpha_bench.models.base import BaseTradingModel

    class MyModel(BaseTradingModel):
        def generate_decision(self, features, context):
            # Implement decision logic
            pass
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class TradingDecision:
    """Structured trading decision output from model.

    Attributes:
        action: Trading action ('buy', 'sell', 'hold')
        symbol: Trading symbol
        size: Position size as fraction of capital (0.0 to 1.0)
        confidence: Model confidence level (0.0 to 1.0)
        rationale: Text explanation for the decision
        metadata: Additional metadata from model
    """

    action: str  # 'buy', 'sell', 'hold'
    symbol: str
    size: float
    confidence: float
    rationale: str
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Validate trading decision."""
        # Validate action
        valid_actions = ["buy", "sell", "hold"]
        if self.action not in valid_actions:
            raise ValueError(
                f"Invalid action '{self.action}'. Must be one of: {valid_actions}"
            )

        # Validate size
        if not 0.0 <= self.size <= 1.0:
            raise ValueError(f"Size must be in [0, 1], got {self.size}")

        # Validate confidence
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be in [0, 1], got {self.confidence}")

        # Normalize hold action size to 0
        if self.action == "hold":
            self.size = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation of decision
        """
        return {
            "action": self.action,
            "symbol": self.symbol,
            "size": self.size,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "metadata": self.metadata or {},
        }


class BaseTradingModel(ABC):
    """Abstract base class for all trading models.

    All LLM-based and baseline trading models must inherit from this class
    and implement the generate_decision method.

    Attributes:
        model_id: Unique identifier for this model
        config: Model configuration from config.yaml
    """

    def __init__(self, model_id: str, config: Dict[str, Any]):
        """Initialize trading model.

        Args:
            model_id: Unique model identifier
            config: Model configuration dictionary
        """
        self.model_id = model_id
        self.config = config
        self.call_count = 0
        self.error_count = 0

        logger.info(f"Initialized model: {model_id}")

    @abstractmethod
    def generate_decision(
        self,
        features: pd.DataFrame,
        context: Optional[Dict[str, Any]] = None,
    ) -> TradingDecision:
        """Generate a trading decision based on features and context.

        This is the main method that must be implemented by all models.
        It receives market features and returns a structured trading decision.

        Args:
            features: DataFrame with feature columns (last row is current state)
            context: Optional context dictionary with additional information:
                - 'portfolio': Current portfolio state
                - 'positions': Current open positions
                - 'capital': Available capital
                - 'timestamp': Current timestamp

        Returns:
            TradingDecision object with action, size, confidence, and rationale

        Raises:
            ModelError: If model fails to generate decision
        """
        pass

    def prepare_prompt(
        self,
        features: pd.DataFrame,
        system_prompt: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Prepare prompt for LLM from features and context.

        Args:
            features: Feature DataFrame
            system_prompt: System prompt template
            context: Context dictionary

        Returns:
            Formatted prompt string
        """
        # Get latest features (last row)
        latest = features.iloc[-1] if len(features) > 0 else {}

        # Format features as text
        features_text = self._format_features(latest)

        # Format context
        context_text = ""
        if context:
            context_text = self._format_context(context)

        # Combine into prompt
        prompt = f"{system_prompt}\n\n"
        prompt += f"Current Market State:\n{features_text}\n\n"
        if context_text:
            prompt += f"Portfolio Context:\n{context_text}\n\n"
        prompt += "Provide your trading decision in JSON format:\n"
        prompt += '{"action": "buy/sell/hold", "size": 0.01, "confidence": 0.75, "rationale": "..."}'

        return prompt

    def _format_features(self, features: pd.Series) -> str:
        """Format features as readable text.

        Args:
            features: Feature series

        Returns:
            Formatted features string
        """
        lines = []
        for key, value in features.items():
            if pd.notna(value):
                if isinstance(value, float):
                    lines.append(f"  {key}: {value:.4f}")
                else:
                    lines.append(f"  {key}: {value}")
        return "\n".join(lines)

    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format context as readable text.

        Args:
            context: Context dictionary

        Returns:
            Formatted context string
        """
        lines = []
        for key, value in context.items():
            if isinstance(value, float):
                lines.append(f"  {key}: {value:.4f}")
            else:
                lines.append(f"  {key}: {value}")
        return "\n".join(lines)

    def validate_decision(self, decision: TradingDecision) -> bool:
        """Validate that decision meets requirements.

        Args:
            decision: Trading decision to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            # Check action
            if decision.action not in ["buy", "sell", "hold"]:
                logger.error(f"Invalid action: {decision.action}")
                return False

            # Check size
            if not 0.0 <= decision.size <= 1.0:
                logger.error(f"Invalid size: {decision.size}")
                return False

            # Check confidence
            if not 0.0 <= decision.confidence <= 1.0:
                logger.error(f"Invalid confidence: {decision.confidence}")
                return False

            # Check risk cap from config
            risk_cap = self.config.get("risk_cap", 0.01)
            if decision.size > risk_cap:
                logger.warning(
                    f"Decision size {decision.size} exceeds risk cap {risk_cap}"
                )
                decision.size = risk_cap

            return True

        except Exception as e:
            logger.error(f"Error validating decision: {e}")
            return False

    def increment_call_count(self):
        """Increment the model call counter."""
        self.call_count += 1

    def increment_error_count(self):
        """Increment the model error counter."""
        self.error_count += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get model usage statistics.

        Returns:
            Dictionary with call_count, error_count, error_rate
        """
        error_rate = self.error_count / self.call_count if self.call_count > 0 else 0.0
        return {
            "model_id": self.model_id,
            "call_count": self.call_count,
            "error_count": self.error_count,
            "error_rate": error_rate,
        }

    def __repr__(self) -> str:
        """String representation of model."""
        return (
            f"{self.__class__.__name__}(model_id={self.model_id}, "
            f"calls={self.call_count}, errors={self.error_count})"
        )


class ModelError(Exception):
    """Raised when model encounters an error."""

    pass


class BaselineModel(BaseTradingModel):
    """Base class for simple baseline models (random, trend-following, etc.)."""

    def __init__(self, model_id: str, config: Dict[str, Any]):
        """Initialize baseline model.

        Args:
            model_id: Model identifier
            config: Model configuration
        """
        super().__init__(model_id, config)
        self.strategy = config.get("strategy", "random")
