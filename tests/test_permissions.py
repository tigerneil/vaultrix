"""Tests for permission system."""

import pytest

from vaultrix.core.permissions import (
    PermissionManager,
    PermissionSet,
    Permission,
    ResourceType,
    PermissionLevel,
    RiskLevel,
    PermissionDeniedException,
)


def test_permission_check_allowed():
    """Test permission check for allowed operation."""
    perm_set = PermissionSet(
        name="test",
        permissions=[
            Permission(
                resource_type=ResourceType.FILESYSTEM,
                level=PermissionLevel.READ,
                paths=["/workspace"],
            )
        ],
    )

    manager = PermissionManager(perm_set)
    assert manager.check_permission(
        ResourceType.FILESYSTEM,
        PermissionLevel.READ,
        "/workspace/test.txt"
    )


def test_permission_check_denied():
    """Test permission check for denied operation."""
    perm_set = PermissionSet(
        name="test",
        permissions=[
            Permission(
                resource_type=ResourceType.FILESYSTEM,
                level=PermissionLevel.READ,
                paths=["/workspace"],
            )
        ],
    )

    manager = PermissionManager(perm_set)
    assert not manager.check_permission(
        ResourceType.FILESYSTEM,
        PermissionLevel.WRITE,  # Higher than allowed
        "/workspace/test.txt"
    )


def test_require_permission_raises():
    """Test that require_permission raises exception when denied."""
    perm_set = PermissionSet(
        name="test",
        permissions=[
            Permission(
                resource_type=ResourceType.NETWORK,
                level=PermissionLevel.NONE,
                enabled=False,
            )
        ],
    )

    manager = PermissionManager(perm_set)
    with pytest.raises(PermissionDeniedException):
        manager.require_permission(
            ResourceType.NETWORK,
            PermissionLevel.READ,
        )


def test_risk_level_determines_approval():
    """Test that high-risk operations require approval."""
    perm_set = PermissionSet(
        name="test",
        permissions=[
            Permission(
                resource_type=ResourceType.PROCESS,
                level=PermissionLevel.EXECUTE,
                risk_level=RiskLevel.HIGH,
            )
        ],
    )

    manager = PermissionManager(perm_set)
    assert manager.requires_approval(
        ResourceType.PROCESS,
        PermissionLevel.EXECUTE
    )


def test_access_log():
    """Test that access attempts are logged."""
    perm_set = PermissionSet(name="test", permissions=[])
    manager = PermissionManager(perm_set)

    manager.check_permission(ResourceType.FILESYSTEM, PermissionLevel.READ)

    log = manager.get_access_log()
    assert len(log) == 1
    assert log[0]["resource_type"] == ResourceType.FILESYSTEM.value
    assert log[0]["allowed"] is False


def test_permission_hierarchy():
    """Test that permission levels follow hierarchy."""
    perm_set = PermissionSet(
        name="test",
        permissions=[
            Permission(
                resource_type=ResourceType.FILESYSTEM,
                level=PermissionLevel.WRITE,
                paths=["/workspace"],
            )
        ],
    )

    manager = PermissionManager(perm_set)

    # WRITE level should allow READ
    assert manager.check_permission(
        ResourceType.FILESYSTEM,
        PermissionLevel.READ,
        "/workspace/file.txt"
    )

    # But not EXECUTE
    assert not manager.check_permission(
        ResourceType.FILESYSTEM,
        PermissionLevel.EXECUTE,
        "/workspace/file.txt"
    )


def test_path_restriction():
    """Test that path restrictions are enforced."""
    perm_set = PermissionSet(
        name="test",
        permissions=[
            Permission(
                resource_type=ResourceType.FILESYSTEM,
                level=PermissionLevel.READ,
                paths=["/workspace/allowed"],
            )
        ],
    )

    manager = PermissionManager(perm_set)

    # Allowed path
    assert manager.check_permission(
        ResourceType.FILESYSTEM,
        PermissionLevel.READ,
        "/workspace/allowed/file.txt"
    )

    # Disallowed path
    assert not manager.check_permission(
        ResourceType.FILESYSTEM,
        PermissionLevel.READ,
        "/workspace/forbidden/file.txt"
    )
