#!/usr/bin/env python3
"""
Custom permissions example for Vaultrix.

This script demonstrates:
1. Creating custom permission sets
2. Testing permission boundaries
3. Handling permission denials
"""

from vaultrix import VaultrixAgent
from vaultrix.core.permissions import (
    PermissionSet,
    Permission,
    ResourceType,
    PermissionLevel,
    RiskLevel,
    PermissionDeniedException,
)


def example_read_only_permissions():
    """Example with read-only filesystem permissions."""
    print("\n📖 Example: Read-Only Permissions")
    print("=" * 50)

    # Create read-only permission set
    read_only_perms = PermissionSet(
        name="read_only_example",
        description="Read-only access to workspace",
        permissions=[
            Permission(
                resource_type=ResourceType.FILESYSTEM,
                level=PermissionLevel.READ,
                paths=["/workspace"],
                risk_level=RiskLevel.LOW,
            )
        ],
    )

    with VaultrixAgent(permission_set=read_only_perms) as agent:
        # This should work (read operation)
        print("\n✓ Testing read operation...")
        result = agent.execute_command("ls -la /workspace")
        print(f"  Success! Found {len(result['stdout'].split())} items")

        # This should fail (write operation)
        print("\n✗ Testing write operation (should fail)...")
        try:
            agent.write_file("/workspace/test.txt", b"test content")
            print("  Unexpected: Write succeeded!")
        except PermissionDeniedException as e:
            print(f"  Expected: Write denied - {e}")


def example_network_whitelist():
    """Example with network access whitelist."""
    print("\n🌐 Example: Network Whitelist Permissions")
    print("=" * 50)

    network_perms = PermissionSet(
        name="network_example",
        description="Network access with whitelist",
        permissions=[
            Permission(
                resource_type=ResourceType.FILESYSTEM,
                level=PermissionLevel.WRITE,
                paths=["/workspace"],
                risk_level=RiskLevel.MEDIUM,
            ),
            Permission(
                resource_type=ResourceType.NETWORK,
                level=PermissionLevel.EXECUTE,
                whitelist=["api.github.com", "pypi.org"],
                risk_level=RiskLevel.HIGH,
            ),
        ],
    )

    with VaultrixAgent(permission_set=network_perms) as agent:
        print("\n✓ Agent created with network whitelist:")
        print("  - api.github.com")
        print("  - pypi.org")

        # Check if network operation requires approval
        requires_approval = agent.permission_manager.requires_approval(
            ResourceType.NETWORK,
            PermissionLevel.EXECUTE
        )
        print(f"\n⚠️  Network access requires approval: {requires_approval}")

        # Get permission summary
        summary = agent.permission_manager.get_summary()
        print(f"\nPermission Summary:")
        print(f"  - Permission Set: {summary['permission_set']}")
        print(f"  - Approval Required For: {summary['approval_required_resources']}")


def example_multi_path_access():
    """Example with multiple path restrictions."""
    print("\n📂 Example: Multi-Path Access")
    print("=" * 50)

    multi_path_perms = PermissionSet(
        name="multi_path_example",
        description="Access to multiple specific paths",
        permissions=[
            Permission(
                resource_type=ResourceType.FILESYSTEM,
                level=PermissionLevel.WRITE,
                paths=["/workspace/data", "/workspace/output"],
                risk_level=RiskLevel.MEDIUM,
            )
        ],
    )

    with VaultrixAgent(permission_set=multi_path_perms) as agent:
        # Create directory structure
        print("\n✓ Setting up directory structure...")
        agent.execute_command("mkdir -p /workspace/data /workspace/output /workspace/forbidden")

        # Test allowed paths
        print("\n✓ Testing allowed path (/workspace/data)...")
        try:
            agent.write_file("/workspace/data/test.txt", b"allowed content")
            print("  Success: Write to /workspace/data allowed")
        except PermissionDeniedException:
            print("  Error: Write was denied (unexpected)")

        print("\n✓ Testing allowed path (/workspace/output)...")
        try:
            agent.write_file("/workspace/output/result.txt", b"output content")
            print("  Success: Write to /workspace/output allowed")
        except PermissionDeniedException:
            print("  Error: Write was denied (unexpected)")

        # Test forbidden path
        print("\n✗ Testing forbidden path (/workspace/forbidden)...")
        try:
            agent.write_file("/workspace/forbidden/test.txt", b"forbidden content")
            print("  Unexpected: Write to forbidden path succeeded!")
        except PermissionDeniedException:
            print("  Expected: Write to /workspace/forbidden denied")

        # Show access log
        print("\n📊 Access Log Summary:")
        access_log = agent.permission_manager.get_access_log()
        total = len(access_log)
        denied = sum(1 for entry in access_log if not entry['allowed'])
        print(f"  - Total attempts: {total}")
        print(f"  - Denied attempts: {denied}")
        print(f"  - Success rate: {((total - denied) / total * 100):.1f}%")


def example_risk_levels():
    """Example demonstrating different risk levels."""
    print("\n⚠️  Example: Risk Levels")
    print("=" * 50)

    risk_demo_perms = PermissionSet(
        name="risk_demo",
        description="Demonstrating risk levels",
        permissions=[
            Permission(
                resource_type=ResourceType.FILESYSTEM,
                level=PermissionLevel.READ,
                risk_level=RiskLevel.LOW,
            ),
            Permission(
                resource_type=ResourceType.FILESYSTEM,
                level=PermissionLevel.WRITE,
                paths=["/workspace"],
                risk_level=RiskLevel.MEDIUM,
            ),
            Permission(
                resource_type=ResourceType.PROCESS,
                level=PermissionLevel.EXECUTE,
                risk_level=RiskLevel.HIGH,
            ),
        ],
    )

    with VaultrixAgent(permission_set=risk_demo_perms) as agent:
        print("\n📊 Risk Level Analysis:")

        resources = [
            (ResourceType.FILESYSTEM, PermissionLevel.READ),
            (ResourceType.FILESYSTEM, PermissionLevel.WRITE),
            (ResourceType.PROCESS, PermissionLevel.EXECUTE),
        ]

        for resource_type, level in resources:
            risk_level = agent.permission_manager.get_risk_level(resource_type)
            requires_approval = agent.permission_manager.requires_approval(resource_type, level)

            print(f"\n  {resource_type.value} ({level.value}):")
            print(f"    - Risk Level: {risk_level.value}")
            print(f"    - Requires Approval: {requires_approval}")


def main():
    print("🔐 Vaultrix - Custom Permissions Examples")
    print("=" * 50)

    try:
        example_read_only_permissions()
        example_network_whitelist()
        example_multi_path_access()
        example_risk_levels()

        print("\n" + "=" * 50)
        print("✅ All examples completed successfully!")
        print("\nKey Takeaways:")
        print("  1. Permissions are granular and path-based")
        print("  2. Operations are checked against permission levels")
        print("  3. Risk levels determine approval requirements")
        print("  4. All access attempts are logged for audit")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
