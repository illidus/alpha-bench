"""Claude Code API integration for alpha-bench.

This module integrates Claude Code's API for generating trading decisions based on
market features and sentiment data.

Usage:
    from alpha_bench.models.claude_code import ClaudeCodeModel

    model = ClaudeCodeModel(model_id, config, system_prompt)
    decision = model.generate_decision(features, context)
"""

import json
import logging
import os
import time
from collections import deque
from typing import Any, Dict, Optional

import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

from alpha_bench.models.base import BaseTradingModel, ModelError, TradingDecision

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter for API calls.

    Attributes:
        requests_per_minute: Maximum requests per minute
        requests: Deque of request timestamps
    """

    def __init__(self, requests_per_minute: int = 50):
        """Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests per minute
        """
        self.requests_per_minute = requests_per_minute
        self.requests = deque()

    def wait_if_needed(self):
        """Wait if rate limit would be exceeded."""
        now = time.time()

        # Remove requests older than 1 minute
        while self.requests and self.requests[0] < now - 60:
            self.requests.popleft()

        # Wait if at limit
        if len(self.requests) >= self.requests_per_minute:
            sleep_time = 60 - (now - self.requests[0])
            if sleep_time > 0:
                logger.debug(f"Rate limit reached, waiting {sleep_time:.2f}s")
                time.sleep(sleep_time)

        self.requests.append(time.time())


class ClaudeCodeModel(BaseTradingModel):
    """Trading model using Claude Code API (Anthropic).

    Attributes:
        api_key: Anthropic API key
        model_name: Claude model name (e.g., 'claude-sonnet-4-5-20250929')
        system_prompt: System prompt template
        max_tokens: Maximum tokens in response
        temperature: Sampling temperature
        rate_limiter: Rate limiter for API calls
    """

    def __init__(
        self,
        model_id: str,
        config: Dict[str, Any],
        system_prompt: str,
    ):
        """Initialize Claude Code model.

        Args:
            model_id: Unique model identifier
            config: Model configuration from config.yaml
            system_prompt: System prompt template text
        """
        super().__init__(model_id, config)

        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        self.model_name = config.get("model_name", "claude-sonnet-4-5-20250929")
        self.system_prompt = system_prompt
        self.max_tokens = config.get("max_tokens", 4096)
        self.temperature = config.get("temperature", 0.2)
        self.timeout = config.get("timeout", 60)

        # Initialize rate limiter
        rate_limit_rpm = config.get("rate_limit_rpm", 50)
        self.rate_limiter = RateLimiter(requests_per_minute=rate_limit_rpm)

        # Initialize Anthropic client
        try:
            from anthropic import Anthropic

            self.client = Anthropic(api_key=self.api_key)
            logger.info(f"Initialized Claude Code model: {model_id}")
        except ImportError:
            raise ImportError(
                "anthropic package required. Install with: pip install anthropic"
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    def generate_decision(
        self,
        features: pd.DataFrame,
        context: Optional[Dict[str, Any]] = None,
    ) -> TradingDecision:
        """Generate trading decision using Claude Code API.

        Args:
            features: DataFrame with feature columns
            context: Optional context dictionary

        Returns:
            TradingDecision object

        Raises:
            ModelError: If API call fails or response is invalid
        """
        self.increment_call_count()

        try:
            # Rate limiting
            self.rate_limiter.wait_if_needed()

            # Prepare prompt
            prompt = self.prepare_prompt(features, self.system_prompt, context)

            logger.debug(f"Calling Claude API for model {self.model_id}")

            # Call Claude API
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=self.system_prompt,
                messages=[{"role": "user", "content": prompt}],
            )

            # Extract response text
            response_text = response.content[0].text

            logger.debug(f"Claude response: {response_text[:200]}...")

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
        """Parse Claude API response into TradingDecision.

        Args:
            response_text: Raw response text from Claude
            context: Context dictionary

        Returns:
            TradingDecision object

        Raises:
            ModelError: If response cannot be parsed
        """
        # Extract JSON from response (may be wrapped in markdown or text)
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
                    "model": self.model_name,
                    "raw_response": response_text[:500],
                },
            )

            return decision

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to parse response: {e}\nResponse: {response_text}")
            raise ModelError(f"Failed to parse response: {e}")

    @staticmethod
    def _extract_json(text: str) -> str:
        """Extract JSON object from text (may be wrapped in markdown).

        Args:
            text: Input text containing JSON

        Returns:
            JSON string

        Raises:
            ValueError: If no JSON found
        """
        # Try to find JSON in markdown code block
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            return text[start:end].strip()

        # Try to find JSON in code block
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

    def prepare_prompt(
        self,
        features: pd.DataFrame,
        system_prompt: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Prepare user prompt for Claude API.

        Overrides base class to format prompt specifically for Claude.

        Args:
            features: Feature DataFrame
            system_prompt: System prompt (used in system parameter)
            context: Context dictionary

        Returns:
            Formatted user prompt string
        """
        # Get latest features (last row)
        latest = features.iloc[-1] if len(features) > 0 else {}

        # Get recent history (last 5 rows)
        history = features.tail(5) if len(features) >= 5 else features

        # Format current state
        current_state = []
        for key, value in latest.items():
            if pd.notna(value):
                if isinstance(value, float):
                    current_state.append(f"  {key}: {value:.6f}")
                else:
                    current_state.append(f"  {key}: {value}")

        # Format context
        context_lines = []
        if context:
            symbol = context.get("symbol", "UNKNOWN")
            capital = context.get("capital", 0.0)
            timestamp = context.get("timestamp", "unknown")

            context_lines.append(f"Symbol: {symbol}")
            context_lines.append(f"Available Capital: ${capital:,.2f}")
            context_lines.append(f"Timestamp: {timestamp}")

        # Build prompt
        prompt = "# Trading Decision Request\n\n"

        if context_lines:
            prompt += "## Portfolio Context\n"
            prompt += "\n".join(context_lines) + "\n\n"

        prompt += "## Current Market Features\n"
        prompt += "\n".join(current_state) + "\n\n"

        prompt += "## Recent History (Last 5 periods)\n"
        prompt += history.to_string() + "\n\n"

        prompt += "## Required Response Format\n"
        prompt += "Please analyze the market data and provide your trading decision in JSON format:\n\n"
        prompt += "```json\n"
        prompt += "{\n"
        prompt += '  "action": "buy/sell/hold",\n'
        prompt += '  "size": 0.01,  // fraction of capital (0.0 to 1.0)\n'
        prompt += '  "confidence": 0.75,  // confidence level (0.0 to 1.0)\n'
        prompt += '  "rationale": "Detailed explanation of your decision"\n'
        prompt += "}\n"
        prompt += "```"

        return prompt
