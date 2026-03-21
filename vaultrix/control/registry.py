"""Registry for control settings — discover and instantiate by name."""

from __future__ import annotations

from typing import Type

from vaultrix.control.base import ControlSetting

SETTING_REGISTRY: dict[str, Type[ControlSetting]] = {}


def register_setting(cls: Type[ControlSetting]) -> Type[ControlSetting]:
    """Class decorator that registers a ControlSetting subclass."""
    SETTING_REGISTRY[cls.__name__] = cls
    return cls


def get_setting(name: str) -> ControlSetting:
    """Instantiate a setting by class name."""
    if name not in SETTING_REGISTRY:
        raise KeyError(f"Unknown setting: {name!r}. Available: {list(SETTING_REGISTRY)}")
    return SETTING_REGISTRY[name]()


def list_settings() -> list[str]:
    """Return the names of all registered settings."""
    return sorted(SETTING_REGISTRY.keys())
