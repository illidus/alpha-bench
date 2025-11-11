"""llama.cpp local model integration for alpha-bench.

This module integrates llama.cpp for running local LLMs for trading decisions.
Requires llama-cpp-python to be installed.

Usage:
    from alpha_bench.models.llama_cpp import LlamaCppModel

    model = LlamaCppModel(model_id, config, system_prompt)
    decision = model.generate_decision(features, context)
"""

import json
import logging
from typing import Any, Dict, Optional

import pandas as pd

from alpha_bench.models.base import BaseTradingModel, ModelError, TradingDecision

logger = logging.getLogger(__name__)


class LlamaCppModel(BaseTradingModel):
    """Trading model using llama.cpp for local inference.

    Attributes:
        model_path: Path to GGUF model file
        system_prompt: System prompt template
        n_ctx: Context window size
        n_threads: Number of CPU threads
        temperature: Sampling temperature
        llama: Loaded llama.cpp model
    """

    def __init__(
        self,
        model_id: str,
        config: Dict[str, Any],
        system_prompt: str,
    ):
        """Initialize llama.cpp model.

        Args:
            model_id: Unique model identifier
            config: Model configuration from config.yaml
            system_prompt: System prompt template text
        """
        super().__init__(model_id, config)

        self.model_path = config.get("model_path")
        if not self.model_path:
            raise ValueError("model_path required for llama_cpp provider")

        self.system_prompt = system_prompt
        self.n_ctx = config.get("n_ctx", 4096)
        self.n_threads = config.get("n_threads", 8)
        self.temperature = config.get("temperature", 0.2)
        self.max_tokens = config.get("max_tokens", 2048)

        # Initialize llama.cpp
        try:
            from llama_cpp import Llama

            self.llama = Llama(
                model_path=self.model_path,
                n_ctx=self.n_ctx,
                n_threads=self.n_threads,
                verbose=False,
            )
            logger.info(f"Initialized llama.cpp model: {model_id}")
        except ImportError:
            raise ImportError(
                "llama-cpp-python required for llama_cpp provider. "
                "Install with: pip install llama-cpp-python"
            )
        except Exception as e:
            raise ModelError(f"Failed to load llama.cpp model: {e}")

    def generate_decision(
        self,
        features: pd.DataFrame,
        context: Optional[Dict[str, Any]] = None,
    ) -> TradingDecision:
        """Generate trading decision using llama.cpp.

        Args:
            features: DataFrame with feature columns
            context: Optional context dictionary

        Returns:
            TradingDecision object

        Raises:
            ModelError: If inference fails
        """
        self.increment_call_count()

        try:
            # Prepare prompt
            prompt = self.prepare_prompt(features, self.system_prompt, context)

            logger.debug(f"Calling llama.cpp for model {self.model_id}")

            # Generate response
            response = self.llama(
                prompt,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                stop=["</s>", "###", "\n\n\n"],
            )

            # Extract response text
            response_text = response["choices"][0]["text"]

            logger.debug(f"llama.cpp response: {response_text[:200]}...")

            # Parse decision from response
            decision = self._parse_response(response_text, context)

            # Validate decision
            if not self.validate_decision(decision):
                raise ModelError(f"Invalid decision from model {self.model_id}")

            return decision

        except Exception as e:
            self.increment_error_count()
            logger.error(f"Error generating decision with {self.model_id}: {e}")
            # Return safe default (hold)
            return TradingDecision(
                action="hold",
                symbol=context.get("symbol", "UNKNOWN") if context else "UNKNOWN",
                size=0.0,
                confidence=0.0,
                rationale=f"Error: {str(e)}",
                metadata={"error": True},
            )

    def _parse_response(
        self, response_text: str, context: Optional[Dict[str, Any]] = None
    ) -> TradingDecision:
        """Parse llama.cpp response into TradingDecision.

        Args:
            response_text: Raw response text from llama.cpp
            context: Context dictionary

        Returns:
            TradingDecision object

        Raises:
            ModelError: If response cannot be parsed
        """
        # Extract JSON from response
        json_str = self._extract_json(response_text)

        try:
            data = json.loads(json_str)

            # Get symbol from context or data
            symbol = "UNKNOWN"
            if context and "symbol" in context:
                symbol = context["symbol"]
            elif "symbol" in data:
                symbol = data["symbol"]

            # Create decision
            decision = TradingDecision(
                action=data.get("action", "hold").lower(),
                symbol=symbol,
                size=float(data.get("size", 0.0)),
                confidence=float(data.get("confidence", 0.5)),
                rationale=data.get("rationale", "No rationale provided"),
                metadata={
                    "model_path": self.model_path,
                    "raw_response": response_text[:500],
                },
            )

            return decision

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to parse response: {e}\nResponse: {response_text}")
            raise ModelError(f"Failed to parse response: {e}")

    @staticmethod
    def _extract_json(text: str) -> str:
        """Extract JSON object from text.

        Args:
            text: Input text containing JSON

        Returns:
            JSON string

        Raises:
            ValueError: If no JSON found
        """
        # Try to find JSON in code block
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            return text[start:end].strip()

        if "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            return text[start:end].strip()

        # Try to find JSON object directly
        if "{" in text and "}" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            return text[start:end].strip()

        raise ValueError("No JSON object found in response")
