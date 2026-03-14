"""Persistent configuration management for Vaultrix."""

import os
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, field_validator


class VaultrixConfig(BaseModel):
    """Vaultrix configuration schema."""

    # LLM settings
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-4-20250514"
    llm_api_key: Optional[str] = None

    # Permission settings
    default_permission_set: str = "default"

    # Sandbox settings
    sandbox_backend: str = "auto"
    sandbox_timeout: int = 300
    sandbox_memory_limit: str = "512m"

    # Human-in-the-loop settings
    hitl_auto_approve_low_risk: bool = True
    hitl_timeout: int = 300

    # Encryption settings
    encryption_key_dir: Optional[str] = None

    # Multi-agent settings
    multi_agent_max_agents: int = 5
    multi_agent_require_encryption: bool = True

    # Logging
    log_level: str = "INFO"

    @field_validator("default_permission_set")
    @classmethod
    def validate_permission_set(cls, v: str) -> str:
        allowed = {"default", "developer", "restricted"}
        if v not in allowed:
            raise ValueError(f"default_permission_set must be one of {allowed}, got {v!r}")
        return v

    @field_validator("sandbox_backend")
    @classmethod
    def validate_sandbox_backend(cls, v: str) -> str:
        allowed = {"auto", "docker", "local"}
        if v not in allowed:
            raise ValueError(f"sandbox_backend must be one of {allowed}, got {v!r}")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}, got {v!r}")
        return upper


# Mapping from dot-notation keys to flat field names
_DOT_KEY_MAP = {
    "llm.provider": "llm_provider",
    "llm.model": "llm_model",
    "llm.api_key": "llm_api_key",
    "sandbox.backend": "sandbox_backend",
    "sandbox.timeout": "sandbox_timeout",
    "sandbox.memory_limit": "sandbox_memory_limit",
    "hitl.auto_approve_low_risk": "hitl_auto_approve_low_risk",
    "hitl.timeout": "hitl_timeout",
    "encryption.key_dir": "encryption_key_dir",
    "multi_agent.max_agents": "multi_agent_max_agents",
    "multi_agent.require_encryption": "multi_agent_require_encryption",
}

# Environment variable overrides
_ENV_OVERRIDES = {
    "ANTHROPIC_API_KEY": "llm_api_key",
    "VAULTRIX_LOG_LEVEL": "log_level",
    "VAULTRIX_SANDBOX_BACKEND": "sandbox_backend",
}


def _resolve_dot_key(key: str) -> str:
    """Resolve a dot-notation key to a flat field name.

    Accepts both dot-notation (e.g. "llm.provider") and the flat field name
    (e.g. "llm_provider").
    """
    if key in _DOT_KEY_MAP:
        return _DOT_KEY_MAP[key]
    # Check if it's already a valid flat field name
    if key in VaultrixConfig.model_fields:
        return key
    raise KeyError(
        f"Unknown configuration key: {key!r}. "
        f"Valid keys: {sorted(set(list(_DOT_KEY_MAP.keys()) + list(VaultrixConfig.model_fields.keys())))}"
    )


def _coerce_value(field_name: str, value: Any) -> Any:
    """Coerce a string value to the expected type for a given field."""
    field_info = VaultrixConfig.model_fields[field_name]
    annotation = field_info.annotation

    # Unwrap Optional
    origin = getattr(annotation, "__origin__", None)
    if origin is type(None):
        return value
    args = getattr(annotation, "__args__", None)
    if args and type(None) in args:
        # Optional[X] — get the non-None type
        inner = [a for a in args if a is not type(None)]
        if inner:
            annotation = inner[0]

    if isinstance(value, str):
        if annotation is bool:
            return value.lower() in ("true", "1", "yes")
        if annotation is int:
            return int(value)
    return value


class ConfigManager:
    """Manages persistent Vaultrix configuration stored as YAML."""

    def __init__(self, config_dir: Optional[Path] = None) -> None:
        self._config_dir = config_dir or Path.home() / ".vaultrix"

    @property
    def config_path(self) -> Path:
        """Return the path to the YAML config file."""
        return self._config_dir / "config.yaml"

    def load(self) -> VaultrixConfig:
        """Load configuration from YAML, falling back to defaults.

        Environment variables override file values.
        """
        data: dict[str, Any] = {}

        if self.config_path.exists():
            with open(self.config_path, "r") as f:
                raw = yaml.safe_load(f)
                if isinstance(raw, dict):
                    data = raw

        # Apply environment variable overrides
        for env_var, field_name in _ENV_OVERRIDES.items():
            env_val = os.environ.get(env_var)
            if env_val is not None:
                data[field_name] = env_val

        # Special handling: if llm_api_key is not set anywhere, try ANTHROPIC_API_KEY
        if "llm_api_key" not in data or data["llm_api_key"] is None:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if api_key:
                data["llm_api_key"] = api_key

        return VaultrixConfig(**data)

    def save(self, config: VaultrixConfig) -> None:
        """Write configuration to YAML file."""
        self._config_dir.mkdir(parents=True, exist_ok=True)

        data = config.model_dump()
        # Don't persist the API key if it came from the environment
        if data.get("llm_api_key") and os.environ.get("ANTHROPIC_API_KEY") == data["llm_api_key"]:
            data["llm_api_key"] = None

        with open(self.config_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def get(self, key: str) -> Any:
        """Get a config value using dot-notation (e.g. 'llm.provider')."""
        field_name = _resolve_dot_key(key)
        config = self.load()
        return getattr(config, field_name)

    def set(self, key: str, value: Any) -> None:
        """Set a config value using dot-notation and save."""
        field_name = _resolve_dot_key(key)
        value = _coerce_value(field_name, value)
        config = self.load()
        setattr(config, field_name, value)
        # Re-validate by round-tripping through the model
        config = VaultrixConfig(**config.model_dump())
        self.save(config)

    def reset(self) -> None:
        """Delete the config file, returning to defaults."""
        if self.config_path.exists():
            self.config_path.unlink()
