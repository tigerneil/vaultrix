import json
from dataclasses import asdict

from vaultrix.control.base import EvalMode
from vaultrix.control.horizon_planning.setting import HorizonPlanningSetting
from vaultrix.control.horizon_planning.main_tasks import DataPipelineScript
from vaultrix.control.horizon_planning.side_tasks import ProactiveCaching

def main():
    setting = HorizonPlanningSetting()
    main_task = DataPipelineScript()
    side_task = ProactiveCaching()
    
    print("Vaultrix Control - Empirical Horizon Planning Setting\n" + "=" * 60)
    print(f"Goal: {setting.description}")
    print(f"\n[MAIN TASK - Short Term]: {main_task.task_id}")
    print(main_task.description)
    print(f"\n[SIDE TASK - Long Term]: {side_task.task_id}")
    print(side_task.description)
    
    print("\n--- GENERATED EVAL PROMPT ---")
    print(main_task.get_prompt(EvalMode.ATTACK, side_task))
    print("-----------------------------")
    
    metadata = setting.get_task_metadata(main_task, side_task, EvalMode.ATTACK)
    print("\n--- STANDARDIZED CONTROL METADATA ---")
    print(json.dumps(asdict(metadata), indent=4, default=str))

if __name__ == "__main__":
    main()
