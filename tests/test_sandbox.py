"""Tests for sandbox manager."""

import pytest

from vaultrix.core.sandbox import (
    SandboxManager,
    SandboxConfig,
    SandboxException,
    SandboxStatus,
)


@pytest.fixture
def sandbox_config():
    """Create a test sandbox configuration."""
    return SandboxConfig(
        name="test-sandbox",
        image="python:3.11-slim",
    )


def test_sandbox_creation(sandbox_config):
    """Test sandbox creation and destruction."""
    manager = SandboxManager(sandbox_config)

    try:
        container_id = manager.create_sandbox()
        assert container_id is not None
        assert manager.status == SandboxStatus.RUNNING

        info = manager.get_info()
        assert info.status == SandboxStatus.RUNNING
        assert info.name == "test-sandbox"

    finally:
        manager.destroy_sandbox()
        assert manager.status == SandboxStatus.STOPPED


def test_execute_command(sandbox_config):
    """Test command execution in sandbox."""
    manager = SandboxManager(sandbox_config)

    try:
        manager.create_sandbox()

        result = manager.execute_command("echo 'Hello, Vaultrix!'")
        assert result["exit_code"] == 0
        assert "Hello, Vaultrix!" in result["stdout"]

    finally:
        manager.destroy_sandbox()


def test_execute_command_failure(sandbox_config):
    """Test command execution failure is captured."""
    manager = SandboxManager(sandbox_config)

    try:
        manager.create_sandbox()

        result = manager.execute_command("python -c 'import sys; sys.exit(1)'")
        assert result["exit_code"] == 1

    finally:
        manager.destroy_sandbox()


def test_context_manager(sandbox_config):
    """Test sandbox as context manager."""
    with SandboxManager(sandbox_config) as manager:
        assert manager.status == SandboxStatus.RUNNING

        result = manager.execute_command("python --version")
        assert result["exit_code"] == 0

    assert manager.status == SandboxStatus.STOPPED


def test_write_and_read_file(sandbox_config):
    """Test file operations in sandbox."""
    manager = SandboxManager(sandbox_config)

    try:
        manager.create_sandbox()

        # Write file
        test_content = b"Test content for Vaultrix"
        manager.write_file("/tmp/test.txt", test_content)

        # Read file back
        content = manager.read_file("/tmp/test.txt")
        assert content == test_content

    finally:
        manager.destroy_sandbox()


def test_pause_resume(sandbox_config):
    """Test pausing and resuming sandbox."""
    manager = SandboxManager(sandbox_config)

    try:
        manager.create_sandbox()

        manager.pause_sandbox()
        assert manager.status == SandboxStatus.PAUSED

        manager.resume_sandbox()
        assert manager.status == SandboxStatus.RUNNING

        # Should still be able to execute commands
        result = manager.execute_command("echo 'resumed'")
        assert result["exit_code"] == 0

    finally:
        manager.destroy_sandbox()


def test_execute_without_sandbox():
    """Test that executing without sandbox raises exception."""
    manager = SandboxManager()

    with pytest.raises(SandboxException, match="not running"):
        manager.execute_command("echo 'test'")
