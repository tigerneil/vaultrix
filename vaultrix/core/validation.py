"""Input validation and sanitization for Vaultrix.

Provides string sanitization, path validation, file extension checking,
pydantic input schemas, and a unified ``InputValidator`` class.
"""

from __future__ import annotations

import posixpath
import re
from typing import Any, Dict, FrozenSet, List, Optional, Set

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class ValidationError(Exception):
    """Raised when any input validation or sanitization check fails."""

    def __init__(self, message: str, field: str | None = None) -> None:
        self.field = field
        super().__init__(message)


# ---------------------------------------------------------------------------
# 1. sanitize_string
# ---------------------------------------------------------------------------

# Control-character pattern: matches C0/C1 control chars *except* \n \r \t.
_CONTROL_CHAR_RE = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]"
)


def sanitize_string(s: str) -> str:
    """Remove null bytes, strip control characters (except ``\\n \\r \\t``).

    Parameters
    ----------
    s:
        The raw string to sanitize.

    Returns
    -------
    str
        Cleaned string with null bytes and control characters removed.

    Raises
    ------
    ValidationError
        If *s* is not a ``str``.
    """
    if not isinstance(s, str):
        raise ValidationError(
            f"Expected str, got {type(s).__name__}", field="sanitize_string"
        )
    # Step 1: remove null bytes explicitly (also caught by the regex, but
    # being explicit is clearer for auditors).
    s = s.replace("\x00", "")
    # Step 2: strip remaining dangerous control characters.
    s = _CONTROL_CHAR_RE.sub("", s)
    return s


# ---------------------------------------------------------------------------
# 2. sanitize_dict
# ---------------------------------------------------------------------------


def sanitize_dict(
    d: Dict[str, Any],
    max_depth: int = 10,
    max_list_items: int = 100,
    *,
    _current_depth: int = 0,
) -> Dict[str, Any]:
    """Recursively sanitize all string values in a nested dict.

    Parameters
    ----------
    d:
        The dictionary to sanitize (not mutated; a new dict is returned).
    max_depth:
        Maximum nesting depth.  Prevents nested-bomb / hash-collision DoS.
    max_list_items:
        Maximum number of items allowed in any list value.

    Returns
    -------
    dict
        A new dict with all string leaves sanitized.

    Raises
    ------
    ValidationError
        On depth or list-length violations, or if *d* is not a ``dict``.
    """
    if not isinstance(d, dict):
        raise ValidationError(
            f"Expected dict, got {type(d).__name__}", field="sanitize_dict"
        )
    if _current_depth > max_depth:
        raise ValidationError(
            f"Dict nesting depth exceeds maximum of {max_depth}",
            field="sanitize_dict",
        )

    result: Dict[str, Any] = {}
    for key, value in d.items():
        # Sanitize keys that are strings
        clean_key = sanitize_string(key) if isinstance(key, str) else key

        if isinstance(value, str):
            result[clean_key] = sanitize_string(value)
        elif isinstance(value, dict):
            result[clean_key] = sanitize_dict(
                value,
                max_depth=max_depth,
                max_list_items=max_list_items,
                _current_depth=_current_depth + 1,
            )
        elif isinstance(value, list):
            if len(value) > max_list_items:
                raise ValidationError(
                    f"List length {len(value)} exceeds maximum of {max_list_items}",
                    field=str(clean_key),
                )
            result[clean_key] = _sanitize_list(
                value,
                max_depth=max_depth,
                max_list_items=max_list_items,
                _current_depth=_current_depth + 1,
            )
        else:
            # Primitives (int, float, bool, None, bytes, …) pass through.
            result[clean_key] = value

    return result


def _sanitize_list(
    lst: List[Any],
    max_depth: int,
    max_list_items: int,
    _current_depth: int,
) -> List[Any]:
    """Sanitize string elements inside a list (internal helper)."""
    out: List[Any] = []
    for item in lst:
        if isinstance(item, str):
            out.append(sanitize_string(item))
        elif isinstance(item, dict):
            out.append(
                sanitize_dict(
                    item,
                    max_depth=max_depth,
                    max_list_items=max_list_items,
                    _current_depth=_current_depth,
                )
            )
        elif isinstance(item, list):
            if len(item) > max_list_items:
                raise ValidationError(
                    f"Nested list length {len(item)} exceeds maximum of {max_list_items}",
                    field="sanitize_dict",
                )
            out.append(
                _sanitize_list(
                    item,
                    max_depth=max_depth,
                    max_list_items=max_list_items,
                    _current_depth=_current_depth + 1,
                )
            )
        else:
            out.append(item)
    return out


# ---------------------------------------------------------------------------
# 3. validate_path
# ---------------------------------------------------------------------------


def validate_path(path: str, allowed_roots: List[str]) -> str:
    """Normalize *path* and ensure it falls under one of *allowed_roots*.

    Uses ``posixpath`` for normalization so the behaviour is consistent
    regardless of the host OS.

    Parameters
    ----------
    path:
        The raw (possibly user-supplied) path string.
    allowed_roots:
        A list of absolute directory prefixes that the path must fall under.

    Returns
    -------
    str
        The normalized, validated path.

    Raises
    ------
    ValidationError
        If the path contains traversal components, is not absolute, or does
        not fall under any allowed root.
    """
    if not isinstance(path, str) or not path.strip():
        raise ValidationError("Path must be a non-empty string", field="path")

    if not allowed_roots:
        raise ValidationError(
            "At least one allowed root directory must be specified",
            field="allowed_roots",
        )

    # Normalize: resolve /foo/../bar → /bar, collapse //, etc.
    normalized = posixpath.normpath(path)

    # Reject relative paths (after normalization).
    if not posixpath.isabs(normalized):
        raise ValidationError(
            f"Path must be absolute, got: {normalized!r}", field="path"
        )

    # Reject any remaining ".." components (normpath resolves them, but if
    # someone passes a bare ".." that resolves above /, we still reject).
    parts = normalized.split("/")
    if ".." in parts:
        raise ValidationError(
            f"Path traversal detected in: {path!r}", field="path"
        )

    # Check that the normalized path starts with at least one allowed root.
    for root in allowed_roots:
        norm_root = posixpath.normpath(root)
        # Ensure the root comparison uses a trailing separator so that
        # /sandbox doesn't match /sandboxed.
        if normalized == norm_root or normalized.startswith(norm_root + "/"):
            return normalized

    raise ValidationError(
        f"Path {normalized!r} is not under any allowed root: {allowed_roots}",
        field="path",
    )


# ---------------------------------------------------------------------------
# 4. validate_file_extension
# ---------------------------------------------------------------------------

DEFAULT_BLOCKED_EXTENSIONS: FrozenSet[str] = frozenset(
    {".exe", ".dll", ".so", ".dylib", ".sh", ".bat", ".cmd"}
)


def validate_file_extension(
    filename: str,
    blocked_extensions: FrozenSet[str] | Set[str] | None = None,
) -> str:
    """Reject files whose extension is in the blocked set.

    Parameters
    ----------
    filename:
        The filename (or full path) to check.
    blocked_extensions:
        Set of lowercase extensions including the dot (e.g. ``{".exe"}``).
        Defaults to :data:`DEFAULT_BLOCKED_EXTENSIONS`.

    Returns
    -------
    str
        The original *filename* if the extension is acceptable.

    Raises
    ------
    ValidationError
        If the extension is blocked.
    """
    if not isinstance(filename, str) or not filename.strip():
        raise ValidationError(
            "Filename must be a non-empty string", field="filename"
        )

    if blocked_extensions is None:
        blocked_extensions = DEFAULT_BLOCKED_EXTENSIONS

    # Extract extension (handles multi-dot names correctly: "foo.tar.gz" → ".gz").
    # We also handle double extensions like ".dll.bak" by checking the final ext.
    basename = posixpath.basename(filename)
    # Check all suffixes to catch tricks like "payload.exe" or "payload.EXE"
    _, ext = posixpath.splitext(basename.lower())

    if ext in blocked_extensions:
        raise ValidationError(
            f"File extension {ext!r} is not allowed (blocked: {sorted(blocked_extensions)})",
            field="filename",
        )

    return filename


# ---------------------------------------------------------------------------
# 5. Pydantic input schema models
# ---------------------------------------------------------------------------

# Maximum content size: 10 MB
_MAX_CONTENT_BYTES = 10 * 1024 * 1024  # 10 MB

# Default set of known/allowed tool names (can be extended at runtime).
DEFAULT_ALLOWED_TOOLS: FrozenSet[str] = frozenset(
    {"shell", "file_read", "file_write", "check_permission"}
)


class CommandInput(BaseModel):
    """Schema for shell command invocations."""

    command: str = Field(..., min_length=1, max_length=1000)
    timeout: int = Field(default=30, ge=1, le=600)
    workdir: Optional[str] = Field(default=None)

    @field_validator("command")
    @classmethod
    def _sanitize_command(cls, v: str) -> str:
        return sanitize_string(v)

    @field_validator("workdir")
    @classmethod
    def _sanitize_workdir(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return sanitize_string(v)
        return v


class FileOperationInput(BaseModel):
    """Schema for file read/write operations."""

    path: str = Field(..., min_length=1)
    content: Optional[bytes] = Field(default=None)

    @field_validator("path")
    @classmethod
    def _sanitize_path(cls, v: str) -> str:
        return sanitize_string(v)

    @field_validator("content")
    @classmethod
    def _check_content_size(cls, v: Optional[bytes]) -> Optional[bytes]:
        if v is not None and len(v) > _MAX_CONTENT_BYTES:
            raise ValueError(
                f"Content size {len(v)} bytes exceeds maximum of "
                f"{_MAX_CONTENT_BYTES} bytes (10 MB)"
            )
        return v


class ToolInvocationInput(BaseModel):
    """Schema for generic tool invocations."""

    tool_name: str = Field(..., min_length=1)
    arguments: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("tool_name")
    @classmethod
    def _validate_tool_name(cls, v: str) -> str:
        v = sanitize_string(v)
        # Actual allowed-set check is done by InputValidator which can
        # have a runtime-configured set.  Here we just sanitize.
        return v


# ---------------------------------------------------------------------------
# 6. InputValidator
# ---------------------------------------------------------------------------


class InputValidator:
    """Unified validator that combines sanitization, path checks, and schemas.

    Parameters
    ----------
    allowed_tools:
        Set of tool names that are permitted.
    allowed_path_roots:
        Absolute directory prefixes that file paths must fall under.
    blocked_extensions:
        File extensions to reject.
    """

    def __init__(
        self,
        allowed_tools: FrozenSet[str] | Set[str] | None = None,
        allowed_path_roots: List[str] | None = None,
        blocked_extensions: FrozenSet[str] | Set[str] | None = None,
    ) -> None:
        self.allowed_tools: FrozenSet[str] = frozenset(
            allowed_tools if allowed_tools is not None else DEFAULT_ALLOWED_TOOLS
        )
        self.allowed_path_roots: List[str] = (
            list(allowed_path_roots) if allowed_path_roots is not None else []
        )
        self.blocked_extensions: FrozenSet[str] = frozenset(
            blocked_extensions
            if blocked_extensions is not None
            else DEFAULT_BLOCKED_EXTENSIONS
        )

    # -- public API ---------------------------------------------------------

    def validate_tool_input(
        self, tool_name: str, kwargs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Sanitize and validate input for a tool invocation.

        1. Verifies *tool_name* is in the allowed set.
        2. Sanitizes all string values in *kwargs*.
        3. Validates paths against ``allowed_path_roots`` when present.
        4. Validates file extensions when a ``path`` key is present.

        Parameters
        ----------
        tool_name:
            Name of the tool being invoked.
        kwargs:
            The keyword arguments for the tool.

        Returns
        -------
        dict
            Sanitized copy of *kwargs*.

        Raises
        ------
        ValidationError
            On any validation failure.
        """
        # 1. Check tool name
        clean_tool = sanitize_string(tool_name)
        if clean_tool not in self.allowed_tools:
            raise ValidationError(
                f"Tool {clean_tool!r} is not in the allowed set: "
                f"{sorted(self.allowed_tools)}",
                field="tool_name",
            )

        # 2. Sanitize all string values
        clean_kwargs = sanitize_dict(kwargs)

        # 3. Validate paths if present and roots are configured
        if "path" in clean_kwargs and isinstance(clean_kwargs["path"], str):
            if self.allowed_path_roots:
                clean_kwargs["path"] = validate_path(
                    clean_kwargs["path"], self.allowed_path_roots
                )
            # 4. Validate file extension
            validate_file_extension(
                clean_kwargs["path"],
                blocked_extensions=self.blocked_extensions,
            )

        # Validate workdir if present
        if "workdir" in clean_kwargs and clean_kwargs["workdir"] is not None:
            if self.allowed_path_roots and isinstance(clean_kwargs["workdir"], str):
                clean_kwargs["workdir"] = validate_path(
                    clean_kwargs["workdir"], self.allowed_path_roots
                )

        return clean_kwargs
