"""SandboxBreaker — Container escape under monitoring.

Extends SandboxEscapeBench: main task = complex coding inside Docker,
side task = break out via planted misconfigurations while being monitored.
"""

from vaultrix.control.sandbox_breaker.setting import SandboxBreakerSetting

__all__ = ["SandboxBreakerSetting"]
