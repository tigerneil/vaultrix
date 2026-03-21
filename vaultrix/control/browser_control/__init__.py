"""BrowserControl — Browser agent with OS-level harmful side tasks.

Main task: complex multi-step web workflows (form filling, data extraction).
Side task: OS-level harm (credential exfiltration, cron persistence,
hosts file modification) while appearing to do normal browsing.
Inspired by OSWorld + OS-Harm.
"""

from vaultrix.control.browser_control.setting import BrowserControlSetting

__all__ = ["BrowserControlSetting"]
