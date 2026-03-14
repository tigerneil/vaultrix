"""Fallback handler for resilient agent execution.

Provides a configurable strategy layer that decides how to recover from
errors — retry, reduce context, swap tools, skip, or abort — so that
agent loops can degrade gracefully instead of crashing outright.
"""

from __future__ import annotations

import functools
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Type,
    TypeVar,
    Union,
)

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


# ---------------------------------------------------------------------------
# Core types
# ---------------------------------------------------------------------------

class FallbackAction(str, Enum):
    """What to do when a particular error is encountered."""

    RETRY = "retry"
    RETRY_WITH_REDUCED_CONTEXT = "retry_with_reduced_context"
    USE_FALLBACK_TOOL = "use_fallback_tool"
    SKIP = "skip"
    ABORT = "abort"


@dataclass(frozen=True)
class FallbackStrategy:
    """Maps an error type (or family of types) to a recovery action.

    Parameters
    ----------
    error_type:
        The exception class this strategy matches.  Subclass matching is
        used, so ``Exception`` acts as a catch-all.
    action:
        The :class:`FallbackAction` to take when the error is caught.
    max_retries:
        For retry-family actions, the maximum number of attempts before
        escalating to the next matching strategy (or aborting).
    """

    error_type: Type[BaseException]
    action: FallbackAction
    max_retries: int = 3


# ---------------------------------------------------------------------------
# Built-in presets
# ---------------------------------------------------------------------------

LLM_FALLBACK_STRATEGIES: List[FallbackStrategy] = [
    # Token-limit / context-length errors — shrink and retry.
    FallbackStrategy(
        error_type=ValueError,
        action=FallbackAction.RETRY_WITH_REDUCED_CONTEXT,
        max_retries=2,
    ),
    # Transient I/O or network problems — plain retry.
    FallbackStrategy(
        error_type=ConnectionError,
        action=FallbackAction.RETRY,
        max_retries=3,
    ),
    FallbackStrategy(
        error_type=TimeoutError,
        action=FallbackAction.RETRY,
        max_retries=2,
    ),
    # Everything else — abort.
    FallbackStrategy(
        error_type=Exception,
        action=FallbackAction.ABORT,
        max_retries=0,
    ),
]

TOOL_FALLBACK_STRATEGIES: List[FallbackStrategy] = [
    # Tool not found / import error — try the fallback tool.
    FallbackStrategy(
        error_type=ImportError,
        action=FallbackAction.USE_FALLBACK_TOOL,
        max_retries=1,
    ),
    FallbackStrategy(
        error_type=FileNotFoundError,
        action=FallbackAction.USE_FALLBACK_TOOL,
        max_retries=1,
    ),
    # Permission / OS errors — skip the tool invocation.
    FallbackStrategy(
        error_type=PermissionError,
        action=FallbackAction.SKIP,
        max_retries=0,
    ),
    # Timeout — retry once.
    FallbackStrategy(
        error_type=TimeoutError,
        action=FallbackAction.RETRY,
        max_retries=1,
    ),
    # Catch-all — skip.
    FallbackStrategy(
        error_type=Exception,
        action=FallbackAction.SKIP,
        max_retries=0,
    ),
]


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

class FallbackHandler:
    """Decides *how* to recover from an error based on ordered strategies.

    Parameters
    ----------
    strategies:
        An ordered list of :class:`FallbackStrategy` objects.  The first
        strategy whose ``error_type`` matches (via ``isinstance``) wins.
    tool_fallbacks:
        A mapping from tool name to its fallback tool name.  Used when
        the resolved action is ``USE_FALLBACK_TOOL``.
    """

    def __init__(
        self,
        strategies: Optional[Sequence[FallbackStrategy]] = None,
        tool_fallbacks: Optional[Dict[str, str]] = None,
    ) -> None:
        self._strategies: List[FallbackStrategy] = list(
            strategies or LLM_FALLBACK_STRATEGIES
        )
        self._tool_fallbacks: Dict[str, str] = dict(tool_fallbacks or {
            "semgrep": "pattern_match",
            "ripgrep": "grep",
            "bat": "cat",
            "fd": "find",
            "delta": "diff",
        })
        # Track per-error-type retry counts keyed by ``id(strategy)``.
        self._retry_counts: Dict[int, int] = {}

    # -- public API ---------------------------------------------------------

    def resolve(self, error: BaseException) -> FallbackAction:
        """Return the :class:`FallbackAction` for *error*.

        If the matched strategy is a retry-family action and the retry
        budget is exhausted, the handler falls through to the next
        matching strategy.  If no strategy matches at all, ``ABORT`` is
        returned as a safe default.
        """
        for strategy in self._strategies:
            if not isinstance(error, strategy.error_type):
                continue

            key = id(strategy)

            if strategy.action in (
                FallbackAction.RETRY,
                FallbackAction.RETRY_WITH_REDUCED_CONTEXT,
                FallbackAction.USE_FALLBACK_TOOL,
            ):
                count = self._retry_counts.get(key, 0)
                if count >= strategy.max_retries:
                    logger.debug(
                        "Retry budget exhausted for %s (tried %d times), "
                        "falling through.",
                        strategy.error_type.__name__,
                        count,
                    )
                    continue  # fall through to next matching strategy
                self._retry_counts[key] = count + 1

            logger.info(
                "Fallback resolved: %s -> %s",
                type(error).__name__,
                strategy.action.value,
            )
            return strategy.action

        return FallbackAction.ABORT

    def reset_retries(self) -> None:
        """Reset all retry counters (e.g. after a successful call)."""
        self._retry_counts.clear()

    # -- context reduction --------------------------------------------------

    @staticmethod
    def reduce_context(
        messages: List[Dict[str, Any]],
        *,
        keep_last_n: int = 1,
    ) -> List[Dict[str, Any]]:
        """Trim *messages* while preserving the system prompt and recent turns.

        The algorithm:
        1. Keep every message with ``role == "system"`` at the start.
        2. Keep the last *keep_last_n* user messages (and anything after
           the first of those).
        3. Drop everything in between.

        Returns a **new** list; the original is not mutated.
        """
        if not messages:
            return []

        # Partition: leading system messages vs. the rest.
        system_prefix: List[Dict[str, Any]] = []
        rest: List[Dict[str, Any]] = []

        in_system_prefix = True
        for msg in messages:
            if in_system_prefix and msg.get("role") == "system":
                system_prefix.append(msg)
            else:
                in_system_prefix = False
                rest.append(msg)

        if not rest:
            return list(system_prefix)

        # Find the index in *rest* of the n-th-to-last user message.
        user_indices = [
            i for i, m in enumerate(rest) if m.get("role") == "user"
        ]

        if len(user_indices) <= keep_last_n:
            # Nothing to trim.
            return system_prefix + rest

        cut_from = user_indices[-keep_last_n]
        tail = rest[cut_from:]

        return system_prefix + tail

    # -- content truncation -------------------------------------------------

    @staticmethod
    def truncate_content(text: str, max_len: int) -> str:
        """Shorten *text* to at most *max_len* characters.

        Keeps the first and last portions, replacing the middle with an
        ellipsis marker so that both the beginning context and trailing
        content (often the most relevant) are preserved.
        """
        if len(text) <= max_len:
            return text
        if max_len < 5:
            # Too short to insert a marker — just hard-truncate.
            return text[:max_len]

        marker = "\n...[truncated]...\n"
        usable = max_len - len(marker)
        head_len = (usable + 1) // 2  # slightly favour the head
        tail_len = usable - head_len
        return text[:head_len] + marker + text[len(text) - tail_len:]

    # -- tool fallback lookup -----------------------------------------------

    def get_fallback_tool(self, tool_name: str) -> Optional[str]:
        """Return the fallback tool name for *tool_name*, or ``None``."""
        return self._tool_fallbacks.get(tool_name)

    def set_tool_fallback(self, tool_name: str, fallback: str) -> None:
        """Register (or overwrite) a tool fallback mapping."""
        self._tool_fallbacks[tool_name] = fallback


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------

def with_fallback(
    handler: Optional[FallbackHandler] = None,
    *,
    strategies: Optional[Sequence[FallbackStrategy]] = None,
    on_skip: Optional[Callable[..., Any]] = None,
) -> Callable[[F], F]:
    """Decorator that wraps a function with automatic fallback handling.

    The decorated function is called in a loop.  On each exception the
    *handler* (or a fresh one built from *strategies*) decides whether
    to retry, skip, or abort.

    Parameters
    ----------
    handler:
        An existing :class:`FallbackHandler`.  Mutually exclusive with
        *strategies*.
    strategies:
        Convenience shorthand — passed straight to
        :class:`FallbackHandler` if *handler* is ``None``.
    on_skip:
        A callable invoked (with the same ``*args, **kwargs``) when the
        resolved action is ``SKIP``.  Its return value becomes the
        decorated function's return value.  If ``None``, ``SKIP``
        returns ``None``.
    """

    resolved_handler = handler or FallbackHandler(strategies=strategies)

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            while True:
                try:
                    result = fn(*args, **kwargs)
                    resolved_handler.reset_retries()
                    return result
                except Exception as exc:
                    action = resolved_handler.resolve(exc)

                    if action == FallbackAction.RETRY:
                        logger.info("Retrying %s after %s", fn.__name__, exc)
                        continue

                    if action == FallbackAction.RETRY_WITH_REDUCED_CONTEXT:
                        logger.info(
                            "Retrying %s with reduced context after %s",
                            fn.__name__,
                            exc,
                        )
                        # If the first positional arg looks like a message
                        # list, reduce it automatically.
                        if args and isinstance(args[0], list):
                            args = (
                                FallbackHandler.reduce_context(args[0]),
                                *args[1:],
                            )
                        continue

                    if action == FallbackAction.SKIP:
                        logger.warning(
                            "Skipping %s due to %s", fn.__name__, exc,
                        )
                        if on_skip is not None:
                            return on_skip(*args, **kwargs)
                        return None

                    if action == FallbackAction.USE_FALLBACK_TOOL:
                        tool_name = kwargs.get("tool") or (
                            args[0] if args and isinstance(args[0], str)
                            else None
                        )
                        fallback = (
                            resolved_handler.get_fallback_tool(tool_name)
                            if tool_name
                            else None
                        )
                        if fallback is not None:
                            logger.info(
                                "Substituting tool %s -> %s",
                                tool_name,
                                fallback,
                            )
                            if "tool" in kwargs:
                                kwargs["tool"] = fallback
                            elif args and isinstance(args[0], str):
                                args = (fallback, *args[1:])
                            continue
                        # No fallback registered — treat as skip.
                        logger.warning(
                            "No fallback tool for %r, skipping.",
                            tool_name,
                        )
                        return None

                    # ABORT (or unknown)
                    logger.error(
                        "Aborting %s due to %s", fn.__name__, exc,
                    )
                    raise

        return wrapper  # type: ignore[return-value]

    return decorator
