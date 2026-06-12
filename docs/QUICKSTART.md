# Quick Start Guide

Get started with Vaultrix in minutes!

## Prerequisites

- Python 3.10 or higher
- Docker 20.10 or higher
- 4GB+ RAM available for Docker

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/vaultrix.git
cd vaultrix
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
pip install -e .
```

### 4. Initialize Sandbox Environment

```bash
./scripts/init_sandbox.sh
```

This will:
- Verify Docker installation
- Pull the base sandbox image
- Create necessary directories

## First Run

### Check System Requirements

```bash
vaultrix check-requirements
```

You should see all requirements marked with ✓.

### Start Your First Agent

```bash
vaultrix start --interactive
```

This launches an interactive Vaultrix session with default sandbox permissions.

### Try Some Commands

In the Vaultrix interactive shell:

```
vaultrix> help
# Shows available commands

vaultrix> status
# Displays agent status

vaultrix> exec echo "Hello from Vaultrix!"
# Executes command in sandbox

vaultrix> exec python --version
# Check Python version in sandbox

vaultrix> logs
# View recent logs

vaultrix> exit
# Exit interactive mode
```

## Understanding Permission Sets

Vaultrix comes with three built-in permission sets:

### Default (Recommended)
```bash
vaultrix start --permission-set default
```

- Filesystem: Write access to `/workspace`
- Network: Disabled
- Process: Disabled
- System: Read-only info

**Use for**: General agent operations with good security

### Restricted (Maximum Security)
```bash
vaultrix start --permission-set restricted
```

- Filesystem: Read-only access to `/workspace/readonly`
- Network: Disabled
- Process: Disabled
- System: No access

**Use for**: Untrusted operations, testing unknown code

### Developer (Extended Access)
```bash
vaultrix start --permission-set developer
```

- Filesystem: Write access to `/workspace`
- Network: Enabled with whitelist
- Process: Read access
- System: Read access

**Use for**: Development and testing (⚠️ Less secure)

## Example: File Operations

Create a Python script to demonstrate Vaultrix's file operations:

```python
from vaultrix import VaultrixAgent
from vaultrix.core.permissions import DEFAULT_SANDBOX_PERMISSIONS

# Create agent with context manager
with VaultrixAgent(permission_set=DEFAULT_SANDBOX_PERMISSIONS) as agent:
    # Write a file
    content = b"Hello from Vaultrix!\n"
    agent.write_file("/workspace/hello.txt", content)
    print("✓ File written")

    # Execute a command to verify
    result = agent.execute_command("cat /workspace/hello.txt")
    print(f"File contents: {result['stdout']}")

    # Get agent status
    status = agent.get_status()
    print(f"\nAgent executed {status['actions_executed']} actions")
```

Run it:
```bash
python examples/file_operations.py
```

## Example: Permission Checking

```python
from vaultrix import VaultrixAgent
from vaultrix.core.permissions import (
    PermissionSet,
    Permission,
    ResourceType,
    PermissionLevel,
    PermissionDeniedException,
)

# Create custom permission set
custom_perms = PermissionSet(
    name="custom",
    permissions=[
        Permission(
            resource_type=ResourceType.FILESYSTEM,
            level=PermissionLevel.READ,
            paths=["/workspace"],
        )
    ],
)

with VaultrixAgent(permission_set=custom_perms) as agent:
    # This will work (read permission)
    result = agent.execute_command("ls /workspace")
    print("✓ Read operation allowed")

    # This will fail (no write permission)
    try:
        agent.write_file("/workspace/test.txt", b"content")
    except PermissionDeniedException as e:
        print(f"✗ Write denied: {e}")
```

## Security Best Practices

### 1. Always Use Sandboxing
Never disable the sandbox for production use. The sandbox provides critical isolation.

### 2. Principle of Least Privilege
Start with minimal permissions and add only what's necessary:

```python
# Good: Specific permissions
perms = PermissionSet(
    permissions=[
        Permission(
            resource_type=ResourceType.FILESYSTEM,
            level=PermissionLevel.READ,
            paths=["/workspace/data"],  # Specific path
        )
    ]
)

# Bad: Overly permissive
# Don't give admin access unless absolutely necessary
```

### 3. Monitor Access Logs
Regularly check access logs for suspicious activity:

```python
agent = VaultrixAgent()
# ... perform operations ...

# Review access log
access_log = agent.permission_manager.get_access_log()
denied = [entry for entry in access_log if not entry['allowed']]
print(f"Denied attempts: {len(denied)}")
```

### 4. Use HITL for High-Risk Operations
When Phase 3 is available, enable human approval for sensitive operations.

## Troubleshooting

### Docker Not Running
```
Error: Failed to connect to Docker
```

**Solution**: Start Docker Desktop or Docker daemon

### Permission Denied Errors
```
PermissionDeniedException: Access denied
```

**Solution**: Check your permission set allows the operation. Use a more permissive set or add specific permissions.

### Sandbox Creation Fails
```
SandboxException: Failed to create sandbox
```

**Solution**:
1. Ensure Docker has enough resources allocated
2. Check Docker disk space
3. Verify image can be pulled: `docker pull python:3.11-slim`

### Import Errors
```
ModuleNotFoundError: No module named 'vaultrix'
```

**Solution**: Install in development mode: `pip install -e .`

## Next Steps

### Explore the Codebase
- Read [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) for design details
- Check [`tests/`](../tests/) for usage examples
- Review permission models in [`vaultrix/core/permissions/`](../vaultrix/core/permissions/)

### Contribute
- See [`CONTRIBUTING.md`](../CONTRIBUTING.md) for guidelines
- Pick an issue from the GitHub repo
- Join our Discord community

### Wait for Phase 2
- VaultHub skill registry
- Pre-audited community skills
- Skill marketplace

### Stay Updated
- Star the repository
- Watch for releases
- Follow [@vaultrix](https://twitter.com/vaultrix) on Twitter

## Getting Help

- **Documentation**: https://docs.vaultrix.dev
- **Discord**: https://discord.gg/vaultrix
- **Issues**: https://github.com/yourusername/vaultrix/issues
- **Email**: team@vaultrix.dev

---

**Ready to build secure autonomous agents!** 🔐
