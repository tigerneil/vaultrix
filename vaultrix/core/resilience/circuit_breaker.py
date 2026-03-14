"""Circuit breaker for resilient LLM and tool calls.

Prevents cascading failures by tracking error rates and temporarily
rejecting calls to unhealthy backends. Inspired by the classic
circuit-breaker pattern (Nygard / DeepAudit).
"""

from __future__ import annotations

import functools
import threading
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar

from pydantic import BaseModel, Field

F = TypeVar("F", bound=Callable[..., Any])


# ── States ────────────────────────────────────────────────────────────────


class CircuitState(str, Enum):
    """The three canonical circuit-breaker states."""

    CLOSED = "closed"  # Normal operation, calls pass through
    OPEN = "open"  # Failures exceeded threshold, calls are rejected
    HALF_OPEN = "half_open"  # Testing whether the backend has recovered


# ── Configuration ─────────────────────────────────────────────────────────


class CircuitBreakerConfig(BaseModel):
    """Tunable knobs for a circuit breaker instance."""

    failure_threshold: int = Field(
        5, ge=1, description="Consecutive failures before opening the circuit"
    )
    recovery_timeout: float = Field(
        30.0, gt=0, description="Seconds to wait before testing recovery (OPEN -> HALF_OPEN)"
    )
    half_open_max_calls: int = Field(
        1, ge=1, description="Max trial calls allowed in HALF_OPEN state"
    )


# ── Preset configs ────────────────────────────────────────────────────────

LLM_CALL_CONFIG = CircuitBreakerConfig(
    failure_threshold=5,
    recovery_timeout=30.0,
    half_open_max_calls=1,
)

TOOL_CALL_CONFIG = CircuitBreakerConfig(
    failure_threshold=3,
    recovery_timeout=60.0,
    half_open_max_calls=1,
)


# ── Stats ─────────────────────────────────────────────────────────────────


class CircuitBreakerStats(BaseModel):
    """Observable metrics for a single circuit breaker."""

    failure_count: int = 0
    success_count: int = 0
    rejection_count: int = 0
    last_failure_time: Optional[float] = Field(
        None, description="Unix timestamp of the most recent failure"
    )
    state: CircuitState = CircuitState.CLOSED


# ── Exceptions ────────────────────────────────────────────────────────────


class CircuitOpenError(Exception):
    """Raised when a call is rejected because the circuit is OPEN."""

    def __init__(self, name: str, retry_after: float) -> None:
        self.name = name
        self.retry_after = retry_after
        super().__init__(
            f"Circuit '{name}' is OPEN. Retry after {retry_after:.1f}s."
        )


# ── Core implementation ──────────────────────────────────────────────────


class CircuitBreaker:
    """Thread-safe circuit breaker.

    Usage — direct::

        cb = CircuitBreaker("openai", config=LLM_CALL_CONFIG)
        try:
            cb.before_call()
            result = call_llm(...)
            cb.record_success()
        except SomeLLMError:
            cb.record_failure()

    Usage — decorator::

        @cb
        def call_llm(...):
            ...
    """

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> None:
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._lock = threading.Lock()

        # Internal mutable state
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._rejection_count = 0
        self._last_failure_time: Optional[float] = None
        self._opened_at: Optional[float] = None
        self._half_open_calls = 0

    # ── Public state queries ──────────────────────────────────────────

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._maybe_transition_to_half_open()
            return self._state

    @property
    def stats(self) -> CircuitBreakerStats:
        with self._lock:
            self._maybe_transition_to_half_open()
            return CircuitBreakerStats(
                failure_count=self._failure_count,
                success_count=self._success_count,
                rejection_count=self._rejection_count,
                last_failure_time=self._last_failure_time,
                state=self._state,
            )

    # ── Call lifecycle ────────────────────────────────────────────────

    def before_call(self) -> None:
        """Gate check before executing a call. Raises *CircuitOpenError* if blocked."""
        with self._lock:
            self._maybe_transition_to_half_open()

            if self._state == CircuitState.OPEN:
                retry_after = self._seconds_until_half_open()
                self._rejection_count += 1
                raise CircuitOpenError(self.name, retry_after)

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.config.half_open_max_calls:
                    self._rejection_count += 1
                    raise CircuitOpenError(self.name, 0.0)
                self._half_open_calls += 1

    def record_success(self) -> None:
        """Record a successful call and close the circuit if recovering."""
        with self._lock:
            self._success_count += 1
            if self._state == CircuitState.HALF_OPEN:
                self._close()
            # In CLOSED state, just reset the consecutive failure counter
            self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call, potentially tripping the circuit open."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                self._open()
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.config.failure_threshold:
                    self._open()

    def reset(self) -> None:
        """Manually force the circuit back to CLOSED. Clears all counters."""
        with self._lock:
            self._close()
            self._failure_count = 0
            self._success_count = 0
            self._rejection_count = 0
            self._last_failure_time = None

    # ── Decorator support ─────────────────────────────────────────────

    def __call__(self, fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            self.before_call()
            try:
                result = fn(*args, **kwargs)
            except Exception:
                self.record_failure()
                raise
            self.record_success()
            return result

        return wrapper  # type: ignore[return-value]

    # ── Internal helpers (must hold self._lock) ───────────────────────

    def _open(self) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = time.monotonic()
        self._half_open_calls = 0

    def _close(self) -> None:
        self._state = CircuitState.CLOSED
        self._opened_at = None
        self._half_open_calls = 0

    def _maybe_transition_to_half_open(self) -> None:
        if self._state == CircuitState.OPEN and self._opened_at is not None:
            elapsed = time.monotonic() - self._opened_at
            if elapsed >= self.config.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0

    def _seconds_until_half_open(self) -> float:
        if self._opened_at is None:
            return 0.0
        remaining = self.config.recovery_timeout - (time.monotonic() - self._opened_at)
        return max(remaining, 0.0)


# ── Registry ──────────────────────────────────────────────────────────────


class CircuitBreakerRegistry:
    """Global, thread-safe registry of named circuit breakers.

    Example::

        registry = CircuitBreakerRegistry()
        llm_cb = registry.get_or_create("openai", config=LLM_CALL_CONFIG)
        tool_cb = registry.get_or_create("shell", config=TOOL_CALL_CONFIG)
    """

    def __init__(self) -> None:
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()

    def get_or_create(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> CircuitBreaker:
        """Return an existing breaker by *name*, or create one with *config*."""
        with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(name, config)
            return self._breakers[name]

    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Return a breaker by name, or ``None`` if it doesn't exist."""
        with self._lock:
            return self._breakers.get(name)

    def remove(self, name: str) -> bool:
        """Remove a breaker. Returns ``True`` if it existed."""
        with self._lock:
            return self._breakers.pop(name, None) is not None

    def reset_all(self) -> None:
        """Reset every registered breaker to CLOSED."""
        with self._lock:
            for cb in self._breakers.values():
                cb.reset()

    def all_stats(self) -> Dict[str, CircuitBreakerStats]:
        """Snapshot of stats for every registered breaker."""
        with self._lock:
            return {name: cb.stats for name, cb in self._breakers.items()}

    @property
    def names(self) -> list[str]:
        with self._lock:
            return list(self._breakers.keys())
