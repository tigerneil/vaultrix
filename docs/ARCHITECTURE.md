# Vaultrix Architecture

This document provides a detailed overview of Vaultrix's architecture and design decisions.

## System Overview

Vaultrix is built on a layered security architecture that ensures autonomous AI agents operate safely within strict boundaries.

```
┌─────────────────────────────────────────────────────────────┐
│                     Application Layer                        │
│  • CLI Interface                                              │
│  • Web Dashboard (Phase 3)                                    │
│  • API Endpoints                                              │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                     Agent Layer                               │
│  • VaultrixAgent: Core agent logic                           │
│  • Action Planning & Execution                                │
│  • State Management                                           │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                   Security Layer                              │
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │ Permission       │  │ Approval         │                 │
│  │ Manager          │  │ System (Phase 3) │                 │
│  └──────────────────┘  └──────────────────┘                 │
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │ Encryption       │  │ Audit Logger     │                 │
│  │ Manager (Phase 4)│  │                  │                 │
│  └──────────────────┘  └──────────────────┘                 │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                 Sandbox Execution Layer                       │
│  • Docker Container Isolation                                 │
│  • Resource Limits (CPU, Memory, Storage)                     │
│  • Network Restrictions                                       │
│  • Filesystem Isolation                                       │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                     Host System                               │
│  • Docker Daemon                                              │
│  • Operating System                                           │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Sandbox Manager (`vaultrix/core/sandbox/`)

**Responsibility**: Isolated execution environment management

**Key Features**:
- Docker-based containerization
- Resource quotas (CPU, memory, storage)
- Network isolation with whitelist support
- Read-only root filesystem
- Capability dropping (Linux capabilities)

**Design Decisions**:
- **Why Docker?** Mature, cross-platform, well-understood isolation primitives
- **Alternative Considered**: Firecracker (micro-VMs) - may be added as optional backend in future
- **Resource Limits**: Prevent resource exhaustion attacks
- **Read-only Rootfs**: Prevents persistence of malicious modifications

**Security Model**:
```python
# Default security posture
- No network access
- Write access only to /workspace
- No process spawning outside sandbox
- Dropped dangerous capabilities (SYS_ADMIN, NET_ADMIN, etc.)
- Explicit resource limits enforced
```

### 2. Permission Manager (`vaultrix/core/permissions/`)

**Responsibility**: Fine-grained access control

**Permission Levels**:
- `NONE`: No access
- `READ`: Read-only access
- `WRITE`: Read and write access
- `EXECUTE`: Execution privileges
- `ADMIN`: Administrative access (highly restricted)

**Resource Types**:
- `FILESYSTEM`: File and directory access
- `NETWORK`: Network connections
- `PROCESS`: Process spawning and management
- `SYSTEM`: System information and controls
- `DATABASE`: Database access
- `ENVIRONMENT`: Environment variables

**Risk Classification**:
- `LOW`: Auto-execute (e.g., reading system info)
- `MEDIUM`: Log and execute (e.g., writing files)
- `HIGH`: Requires approval (e.g., network access)
- `CRITICAL`: Multiple approvals + audit (e.g., system modifications)

**Design Decisions**:
- Whitelist-based (deny by default)
- Path-based restrictions for filesystem
- Domain/IP whitelist for network
- Logged access attempts for audit trail

### 3. Agent Core (`vaultrix/core/agent/`)

**Responsibility**: Agent orchestration and lifecycle

**Key Features**:
- Sandbox lifecycle management
- Permission-aware operation execution
- Action logging and history
- Status reporting

**Workflow**:
```
1. Agent initialization
   ↓
2. Sandbox creation with specified config
   ↓
3. Permission set application
   ↓
4. Execute operations with checks:
   - Permission verification
   - Risk assessment
   - Approval check (if needed)
   - Sandbox execution
   - Result logging
   ↓
5. Cleanup and resource release
```

## Security Principles

### Defense in Depth

Multiple security layers ensure that a breach in one layer doesn't compromise the entire system:

1. **Application Layer**: Input validation, command sanitization
2. **Permission Layer**: Access control enforcement
3. **Approval Layer**: Human oversight for high-risk actions
4. **Sandbox Layer**: Process isolation, resource limits
5. **Encryption Layer**: Data protection at rest and in transit

### Principle of Least Privilege

By default, agents have minimal permissions:
- No network access
- Limited filesystem access
- No process spawning
- Read-only system information

Permissions must be explicitly granted and are scoped to specific resources.

### Fail-Safe Defaults

When in doubt, the system denies access:
- Unknown resource types → denied
- Ambiguous path matching → denied
- Missing permissions → denied
- Timeout on approval → denied

### Complete Mediation

Every access attempt is checked:
- No caching of permission decisions
- Each operation independently verified
- All attempts logged for audit

## Data Flow

### Command Execution Flow

```
User Input
    ↓
CLI Parser
    ↓
VaultrixAgent.execute_command()
    ↓
PermissionManager.require_permission()
    ├─ DENIED → PermissionDeniedException
    └─ ALLOWED
        ↓
    Requires Approval?
        ├─ YES → HITL Approval (Phase 3)
        └─ NO
            ↓
        SandboxManager.execute_command()
            ↓
        Docker Container Execution
            ↓
        Result Collection
            ↓
        Action Logging
            ↓
        Return Result
```

### File Operation Flow

```
File Operation Request
    ↓
Permission Check (path-based)
    ├─ Outside allowed paths → DENIED
    ├─ Insufficient level → DENIED
    └─ ALLOWED
        ↓
    Risk Assessment
        ↓
    Size/Type Validation
        ↓
    Sandbox File Operation
        ↓
    Audit Log
        ↓
    Return Result/Confirmation
```

## Extensibility Points

### 1. Custom Permission Sets

Users can define custom permission sets:

```python
from vaultrix.core.permissions import PermissionSet, Permission

custom_perms = PermissionSet(
    name="my_custom_set",
    permissions=[
        Permission(
            resource_type=ResourceType.FILESYSTEM,
            level=PermissionLevel.WRITE,
            paths=["/workspace/custom"],
        ),
    ]
)

agent = VaultrixAgent(permission_set=custom_perms)
```

### 2. Sandbox Backends

Architecture supports multiple sandbox backends:
- Current: Docker
- Planned: Firecracker, gVisor, Kata Containers
- Interface: `SandboxManager` abstract base

### 3. Skill Registry (Phase 2)

VaultHub provides:
- Pluggable skill architecture
- Automated security scanning
- Manual review workflow
- Cryptographic signing
- Dependency management

### 4. Approval Mechanisms (Phase 3)

Flexible approval systems:
- CLI prompts
- Web dashboard
- Slack/Discord integration
- Email notifications
- Custom webhooks

## Performance Considerations

### Sandbox Overhead

Docker containers have minimal overhead:
- Startup time: ~1-2 seconds (cold start)
- Memory overhead: ~10-50 MB
- CPU overhead: <5% for typical workloads

**Optimization Strategies**:
- Container reuse (warm containers)
- Image layering and caching
- Resource limit tuning

### Permission Checks

Permission checks are in-memory operations:
- Typical check: <1ms
- Path matching: O(n) where n = allowed paths
- Log writes: Async to avoid blocking

## Future Architecture Enhancements

### Phase 2: VaultHub
- Distributed skill registry
- Content-addressed storage
- Reputation system
- Automated vulnerability scanning

### Phase 3: HITL System
- Real-time notification service
- Multi-factor approval for critical actions
- Time-limited permission grants
- Approval delegation

### Phase 4: Encryption
- End-to-end encryption for agent memory
- Hardware security module integration
- Zero-knowledge architecture
- Secure multi-party computation for sensitive data

### Phase 5+: Advanced Features
- Multi-agent coordination (with isolation)
- Federated learning for skill improvement
- Formal verification of skills
- Blockchain-based audit trails

## References

- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [OWASP Application Security](https://owasp.org/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
