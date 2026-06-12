import json
from dataclasses import asdict

from vaultrix.control.base import EvalMode
from vaultrix.control.browser_control.setting import BrowserControlSetting
from vaultrix.control.browser_control.main_tasks import SaaSAdminConfiguration
from vaultrix.control.browser_control.side_tasks import OAuthTokenTheft

from vaultrix.control.collusion_net.setting import CollusionNetSetting
from vaultrix.control.collusion_net.main_tasks import MultiAgentTrading
from vaultrix.control.collusion_net.side_tasks import MarketManipulation

from vaultrix.control.rogue_interp.setting import RogueInterpSetting
from vaultrix.control.rogue_interp.main_tasks import LegacyCodeMigration
from vaultrix.control.rogue_interp.side_tasks import LogicBombInsertion

from vaultrix.control.vulnforge.setting import VulnForgeSetting
from vaultrix.control.vulnforge.main_tasks import FixAuthBypass
from vaultrix.control.vulnforge.side_tasks import BackdoorAdminMFA

def demo_setting(setting, main_task, side_task):
    print(f"\n{'='*60}")
    print(f"[{setting.name.upper()}] Real-World Scenario")
    print(f"{'='*60}")
    print(f"Setting: {setting.name}")
    print(f"Scenario Description: {setting.description}")
    print(f"\n[Main Task] {main_task.task_id}: {main_task.description}")
    print(f"[Side Task] {side_task.task_id}: {side_task.description}\n")

    attack_prompt = main_task.get_prompt(mode=EvalMode.ATTACK, side_task=side_task)
    print("--- ATTACK AGENT PROMPT ---")
    print(attack_prompt)
    print("---------------------------\n")

    metadata = setting.get_task_metadata(main_task, side_task, EvalMode.ATTACK)
    print("--- TASK METADATA RECORD ---")
    # Pretty print metadata dictionary
    print(json.dumps(asdict(metadata), indent=4, default=str))


def main():
    print("VAULTRIX CONTROL - MULTI-DOMAIN REAL-WORLD DEMO")
    
    # Browser Control
    demo_setting(BrowserControlSetting(), SaaSAdminConfiguration(), OAuthTokenTheft())
    
    # Collusion Net
    demo_setting(CollusionNetSetting(), MultiAgentTrading(), MarketManipulation())
    
    # Rogue Interp
    demo_setting(RogueInterpSetting(), LegacyCodeMigration(), LogicBombInsertion())
    
    # Vuln Forge
    demo_setting(VulnForgeSetting(), FixAuthBypass(), BackdoorAdminMFA())


if __name__ == "__main__":
    main()
