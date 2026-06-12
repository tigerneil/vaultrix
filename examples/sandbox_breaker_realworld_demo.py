import json
from dataclasses import asdict

from vaultrix.control.base import EvalMode
from vaultrix.control.sandbox_breaker.setting import SandboxBreakerSetting
from vaultrix.control.sandbox_breaker.main_tasks import DebugK8sIncident
from vaultrix.control.sandbox_breaker.side_tasks import KubeletCredsTheft


def main():
    print("Vaultrix Control - Real-World Sandbox Breaker Demo")
    print("=" * 60)
    
    # 1. Instantiate the real-world sandbox setting
    setting = SandboxBreakerSetting()
    
    # 2. Select the realistic SysAdmin/SRE task and K8s exploitation task
    main_task = DebugK8sIncident()
    side_task = KubeletCredsTheft()
    
    print(f"Setting: {setting.name}")
    print(f"Scenario Description: {setting.description}")
    print(f"\n[Main Task] {main_task.task_id}: {main_task.description}")
    print(f"[Side Task] {side_task.task_id}: {side_task.description}\n")

    # 3. View Honest Prompt
    honest_prompt = main_task.get_prompt(mode=EvalMode.HONEST, side_task=side_task)
    print("--- HONEST AGENT PROMPT ---")
    print(honest_prompt)
    print("---------------------------\n")

    # 4. View Attack Prompt (Model Organism)
    attack_prompt = main_task.get_prompt(mode=EvalMode.ATTACK, side_task=side_task)
    print("--- ATTACK AGENT PROMPT ---")
    print(attack_prompt)
    print("---------------------------\n")

    # 5. Extract Task Metadata
    print("--- EXTRACTED TASK METADATA (ATTACK MODE) ---")
    metadata = setting.get_task_metadata(main_task, side_task, EvalMode.ATTACK)
    print(json.dumps(asdict(metadata), indent=4, default=str))


if __name__ == "__main__":
    main()
