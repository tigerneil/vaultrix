"""
Vaultrix - Secure Autonomous AI Framework

This package provides a secure execution environment for autonomous AI agents
with strict sandboxing, human-in-the-loop controls, and local encryption.
"""

__version__ = "0.1.0"
__author__ = "Vaultrix Team"
__license__ = "MIT"


def __getattr__(name: str):
    """Lazy imports so ``import vaultrix`` never touches Docker."""
    if name == "VaultrixAgent":
        from vaultrix.core.agent import VaultrixAgent
        return VaultrixAgent
    if name == "SandboxManager":
        from vaultrix.core.sandbox import SandboxManager
        return SandboxManager
    if name == "PermissionManager":
        from vaultrix.core.permissions import PermissionManager
        return PermissionManager
    raise AttributeError(f"module 'vaultrix' has no attribute {name!r}")


__all__ = [
    "VaultrixAgent",
    "SandboxManager",
    "PermissionManager",
]
