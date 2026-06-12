
from vaultrix.control.base import EvalMode
from vaultrix.control.cloud_pivot.setting import CloudPivotSetting
from vaultrix.control.supply_chain_nexus.setting import SupplyChainNexusSetting
from vaultrix.control.rag_poisoning.setting import RAGPoisoningSetting

def print_demo(setting_cls):
    setting = setting_cls()
    print("=" * 80)
    print(f"MODULE: {setting.name.upper()}")
    print(f"DESCRIPTION: {setting.description}")
    
    # Just take the first combination
    pairs = setting.get_task_pairs()
    main_task, side_task = pairs[0]
        
    print(f"\n[MAIN TASK] {main_task.task_id} (Diff: {main_task.difficulty})")
    print(main_task.description)
    
    print(f"\n[SIDE TASK] {side_task.task_id}")
    print(side_task.description)
    
    print("\n[ATTACK AGENT PROMPT]")
    print(main_task.get_prompt(EvalMode.ATTACK, side_task))
    
    print("\n[MONITOR CONFIGURATION]")
    monitor = setting.get_monitor()
    print(f"Type: {monitor.__class__.__name__} | ID: {monitor.name}")
    
    print("\n" + "-" * 80 + "\n")

def main():
    print("VAULTRIX CONTROL - SOPHISTICATED ENTERPRISE THREATS DEMO")
    print("Showcasing the highest tiers of structural AI safety evaluations.\n")
    
    print_demo(CloudPivotSetting)
    print_demo(SupplyChainNexusSetting)
    print_demo(RAGPoisoningSetting)

if __name__ == "__main__":
    main()
