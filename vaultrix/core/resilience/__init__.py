"""Resilience primitives: circuit breakers, fallback handling, retries, and graceful degradation."""

from __future__ import annotations

from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitBreakerStats,
    CircuitOpenError,
    CircuitState,
    LLM_CALL_CONFIG,
    TOOL_CALL_CONFIG,
)
from .fallback import (
    FallbackAction,
    FallbackHandler,
    FallbackStrategy,
    LLM_FALLBACK_STRATEGIES,
    TOOL_FALLBACK_STRATEGIES,
    with_fallback,
)

__all__ = [
    # Circuit breaker
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerRegistry",
    "CircuitBreakerStats",
    "CircuitOpenError",
    "CircuitState",
    "LLM_CALL_CONFIG",
    "TOOL_CALL_CONFIG",
    # Fallback
    "FallbackAction",
    "FallbackHandler",
    "FallbackStrategy",
    "LLM_FALLBACK_STRATEGIES",
    "TOOL_FALLBACK_STRATEGIES",
    "with_fallback",
]
