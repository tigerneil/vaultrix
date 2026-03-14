#!/usr/bin/env python3
"""
Quick demo of Vaultrix functionality.
This demonstrates the core features without requiring full installation.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from vaultrix.core.permissions import (
    PermissionManager,
    PermissionSet,
    Permission,
    ResourceType,
    PermissionLevel,
    RiskLevel,
    DEFAULT_SANDBOX_PERMISSIONS,
)

def print_section(title):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def demo_permission_system():
    """Demonstrate the permission system."""
    print_section("Vaultrix Permission System Demo")

    # Create permission manager
    pm = PermissionManager(DEFAULT_SANDBOX_PERMISSIONS)

    print(f"\n✓ Permission Manager initialized")
    print(f"  Permission Set: {pm.permission_set.name}")
    print(f"  Description: {pm.permission_set.description}")

    # Test various permission checks
    print("\n📋 Testing Permission Checks:")

    test_cases = [
        ("Read /workspace/file.txt", ResourceType.FILESYSTEM, PermissionLevel.READ, "/workspace/file.txt"),
        ("Write /workspace/output.txt", ResourceType.FILESYSTEM, PermissionLevel.WRITE, "/workspace/output.txt"),
        ("Execute network request", ResourceType.NETWORK, PermissionLevel.EXECUTE, None),
        ("Spawn process", ResourceType.PROCESS, PermissionLevel.EXECUTE, None),
        ("Read system info", ResourceType.SYSTEM, PermissionLevel.READ, None),
    ]

    for desc, resource, level, path in test_cases:
        allowed = pm.check_permission(resource, level, path)
        status = "✅ ALLOWED" if allowed else "❌ DENIED"
        risk_level = pm.get_risk_level(resource)
        risk = risk_level if isinstance(risk_level, str) else risk_level.value
        risk = risk.upper()
        approval = "⚠️  Requires Approval" if pm.requires_approval(resource, level) else ""
        print(f"  {status:12} - {desc:30} [Risk: {risk}] {approval}")

    # Show access log
    print("\n📊 Access Log Summary:")
    summary = pm.get_summary()
    print(f"  Total attempts: {summary['total_access_attempts']}")
    print(f"  Denied: {summary['denied_attempts']}")
    print(f"  High-risk resources: {', '.join(summary['approval_required_resources'])}")

def demo_custom_permissions():
    """Demonstrate custom permission configuration."""
    print_section("Custom Permission Configuration")

    # Create a custom permission set
    custom_perms = PermissionSet(
        name="demo_custom",
        description="Custom permissions for demo",
        permissions=[
            Permission(
                resource_type=ResourceType.FILESYSTEM,
                level=PermissionLevel.WRITE,
                paths=["/workspace/data", "/workspace/output"],
                risk_level=RiskLevel.MEDIUM,
            ),
            Permission(
                resource_type=ResourceType.NETWORK,
                level=PermissionLevel.EXECUTE,
                whitelist=["api.anthropic.com"],
                risk_level=RiskLevel.HIGH,
            ),
        ]
    )

    print(f"\n✓ Custom Permission Set Created")
    print(f"  Name: {custom_perms.name}")
    print(f"  Permissions: {len(custom_perms.permissions)}")

    pm = PermissionManager(custom_perms)

    print("\n📋 Testing Custom Permissions:")

    test_cases = [
        ("Write to /workspace/data/file.txt", ResourceType.FILESYSTEM, PermissionLevel.WRITE, "/workspace/data/file.txt"),
        ("Write to /workspace/forbidden/file.txt", ResourceType.FILESYSTEM, PermissionLevel.WRITE, "/workspace/forbidden/file.txt"),
        ("Network to api.anthropic.com", ResourceType.NETWORK, PermissionLevel.EXECUTE, "api.anthropic.com"),
    ]

    for desc, resource, level, path in test_cases:
        allowed = pm.check_permission(resource, level, path)
        status = "✅ ALLOWED" if allowed else "❌ DENIED"
        print(f"  {status:12} - {desc}")

def demo_risk_levels():
    """Demonstrate risk level system."""
    print_section("Risk Level Classification")

    print("\n🔒 Vaultrix Risk Levels:")
    print("  • LOW      - Auto-execute (e.g., read operations)")
    print("  • MEDIUM   - Log and execute (e.g., file writes)")
    print("  • HIGH     - Require approval (e.g., network access)")
    print("  • CRITICAL - Multiple approvals + audit (e.g., system mods)")

    print("\n📊 Permission Set Risk Profile:")
    pm = PermissionManager(DEFAULT_SANDBOX_PERMISSIONS)

    risk_counts = {}
    for perm in pm.permission_set.permissions:
        risk_level = perm.risk_level
        risk = risk_level if isinstance(risk_level, str) else risk_level.value
        risk_counts[risk] = risk_counts.get(risk, 0) + 1

    for risk, count in sorted(risk_counts.items()):
        print(f"  {risk.upper():8} - {count} permission(s)")

def main():
    """Run all demos."""
    print("\n🔐 Vaultrix - Secure Autonomous AI Framework")
    print("Phase 1 Demo: Core Security Features\n")

    try:
        demo_permission_system()
        demo_custom_permissions()
        demo_risk_levels()

        print_section("Demo Complete!")
        print("\n✅ All demos completed successfully!")
        print("\nNext steps:")
        print("  • Review docs/QUICKSTART.md for full tutorial")
        print("  • Try examples/basic_usage.py for agent demo")
        print("  • Explore vaultrix/core/ for implementation details")
        print("\n🔐 Vaultrix: Autonomous AI, Safely Unleashed!\n")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
