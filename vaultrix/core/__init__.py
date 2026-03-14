"""Core Vaultrix components."""


def __getattr__(name: str):
    """Lazy imports to avoid Docker dependency at import time."""
    if name == "VaultrixAgent":
        from vaultrix.core.agent import VaultrixAgent
        return VaultrixAgent
    if name == "SandboxManager":
        from vaultrix.core.sandbox import SandboxManager
        return SandboxManager
    if name == "PermissionManager":
        from vaultrix.core.permissions import PermissionManager
        return PermissionManager
    raise AttributeError(f"module 'vaultrix.core' has no attribute {name!r}")


__all__ = [
    "VaultrixAgent",
    "SandboxManager",
    "PermissionManager",
]
