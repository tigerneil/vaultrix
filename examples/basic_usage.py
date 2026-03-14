#!/usr/bin/env python3
"""
Basic usage example for Vaultrix.

This script demonstrates:
1. Creating a Vaultrix agent
2. Executing commands in the sandbox
3. File operations
4. Status monitoring
"""

from vaultrix import VaultrixAgent
from vaultrix.core.permissions import DEFAULT_SANDBOX_PERMISSIONS


def main():
    print("🔐 Vaultrix - Basic Usage Example\n")

    # Create and start agent using context manager
    with VaultrixAgent(permission_set=DEFAULT_SANDBOX_PERMISSIONS) as agent:
        print(f"✓ Agent started: {agent.agent_id}\n")

        # Example 1: Execute a simple command
        print("Example 1: Execute command")
        print("-" * 40)
        result = agent.execute_command("echo 'Hello from Vaultrix!'")
        print(f"Output: {result['stdout'].strip()}")
        print(f"Exit code: {result['exit_code']}\n")

        # Example 2: Check Python version in sandbox
        print("Example 2: Check Python version")
        print("-" * 40)
        result = agent.execute_command("python --version")
        print(f"Python version: {result['stdout'].strip()}\n")

        # Example 3: Write and read a file
        print("Example 3: File operations")
        print("-" * 40)
        content = b"Vaultrix is awesome!\nSecure AI agents for everyone."
        agent.write_file("/workspace/message.txt", content)
        print("✓ File written to /workspace/message.txt")

        result = agent.execute_command("cat /workspace/message.txt")
        print(f"File contents:\n{result['stdout']}")

        # Example 4: List workspace
        print("Example 4: List workspace")
        print("-" * 40)
        result = agent.execute_command("ls -lh /workspace")
        print(result['stdout'])

        # Example 5: Get agent status
        print("Example 5: Agent status")
        print("-" * 40)
        status = agent.get_status()
        print(f"Agent ID: {status['agent_id']}")
        print(f"Uptime: {status['uptime_seconds']:.1f}s")
        print(f"Sandbox Status: {status['sandbox']['status']}")
        print(f"Actions Executed: {status['actions_executed']}")
        print(f"Permission Set: {status['permissions']['permission_set']}")

        print("\n✓ All examples completed successfully!")

    print("\n✓ Agent stopped and cleaned up")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
