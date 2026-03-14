# Building Vaultrix: A Secure Framework for Autonomous AI Agents

*How we built defense-in-depth security for AI agents that actually works*

---

The promise of autonomous AI agents is immense — systems that can reason, plan, and act on your behalf. But with that power comes a fundamental question: **how do you let an AI agent execute code, access files, and make network requests without risking your entire system?**

That's why we built **Vaultrix** — a secure, sandboxed, human-guided framework for running autonomous AI agents. In this post, we'll walk through the architecture, the security model, and the design decisions that make it work.

## The Problem: Autonomous AI Without Guardrails

Today's AI agents are increasingly capable. Give one a goal like "organize my project files" or "set up a CI pipeline," and it can reason through the steps, write code, and execute commands. But most agent frameworks treat security as an afterthought:

- Agents run with the same permissions as the user
- No isolation between the agent and the host system
- No audit trail of what the agent actually did
- No mechanism to pause and ask "are you sure?" before destructive actions

A single hallucinated `rm -rf /` or an exfiltration of `.env` files, and you're in trouble. We needed something better.

## Vaultrix's Approach: Defense in Depth

Vaultrix doesn't rely on a single security mechanism. Instead, it layers five independent defenses:

```
Layer 1: Input Validation      — sanitize commands, validate paths
Layer 2: Permission Control    — fine-grained, whitelist-based access
Layer 3: Human Approval        — HITL gates for high-risk actions
Layer 4: Sandbox Isolation     — containerized execution environments
Layer 5: Encryption at Rest    — local key management for agent data
```

If any single layer fails, the others still protect you. Let's look at each one.

## The Permission System: Deny by Default

At the heart of Vaultrix is a granular permission model. Every resource type — filesystem, network, process, system, database, environment — has an explicit permission level:

```python
class PermissionLevel(str, Enum):
    NONE = "none"       # No access
    READ = "read"       # Read-only
    WRITE = "write"     # Read + Write
    EXECUTE = "execute" # Read + Write + Execute
    ADMIN = "admin"     # Full control
```

Levels are hierarchical: `WRITE` implicitly grants `READ`. But the key principle is **deny by default** — if a permission isn't explicitly granted, access is refused.

Here's what a permission set looks like in practice:

```python
DEFAULT_SANDBOX_PERMISSIONS = PermissionSet(
    name="default_sandbox",
    description="Default secure sandbox permissions",
    permissions=[
        Permission(
            resource_type=ResourceType.FILESYSTEM,
            level=PermissionLevel.WRITE,
            paths=["/workspace", "/workspace/output"],
            risk_level=RiskLevel.MEDIUM,
        ),
        Permission(
            resource_type=ResourceType.NETWORK,
            level=PermissionLevel.NONE,
            risk_level=RiskLevel.HIGH,
        ),
        Permission(
            resource_type=ResourceType.PROCESS,
            level=PermissionLevel.NONE,
            risk_level=RiskLevel.CRITICAL,
        ),
        Permission(
            resource_type=ResourceType.SYSTEM,
            level=PermissionLevel.READ,
            risk_level=RiskLevel.LOW,
        ),
    ]
)
```

The agent can read and write files in `/workspace`, read system info, and that's it. No network. No process spawning. No escape hatches.

### Path Traversal Prevention

One of the subtlest security concerns is path traversal — an agent requesting access to `/workspace/../../../etc/passwd`. Vaultrix normalizes all paths before matching:

```python
def _safe_path_match(requested: str, allowed: str) -> bool:
    req = posixpath.normpath(requested)
    base = posixpath.normpath(allowed)
    return req == base or req.startswith(base + "/")
```

The `normpath` call collapses `..` segments, and the `+ "/"` boundary check prevents `/workspace-evil` from matching `/workspace`. We have five dedicated test cases for path traversal attacks alone.

### Rate Limiting and Expiry

Permissions can be rate-limited (e.g., max 10 filesystem operations per minute) and time-bounded (expires at a specific UTC timestamp). This prevents runaway agents from exhausting resources and supports temporary elevated access for specific tasks.

## Risk Classification: When to Ask a Human

Not all actions are equal. Reading a file is low-risk. Deleting one is high-risk. Vaultrix classifies every operation into four risk levels:

| Risk Level | Action | Example |
|-----------|--------|---------|
| **LOW** | Auto-execute | Read files, check system info |
| **MEDIUM** | Log and execute | Write to workspace |
| **HIGH** | Require approval | Network requests |
| **CRITICAL** | Multiple approvals | System modifications, process spawning |

When an agent attempts a HIGH or CRITICAL operation, Vaultrix pauses execution and asks the user for explicit confirmation. The agent can't bypass this — it's enforced at the permission layer, not the agent layer.

## Sandboxed Execution: Container Isolation

Even with perfect permissions, defense in depth means we don't trust the permission layer alone. Every agent runs inside an isolated sandbox.

Vaultrix auto-detects the best available backend:

```python
def _detect_backend():
    try:
        import docker
        client = docker.from_env()
        client.ping()
        return DockerBackend()  # Full container isolation
    except Exception:
        return LocalBackend()   # Subprocess isolation for development
```

The Docker backend enforces:

- **CPU and memory limits** (default: 1 core, 512MB RAM)
- **Read-only root filesystem**
- **Dropped Linux capabilities** (SYS_ADMIN, NET_ADMIN, SYS_MODULE, SYS_RAWIO)
- **No privilege escalation** (`no-new-privileges` security option)
- **Network disabled by default** with domain whitelisting when enabled
- **Process limits** (max 50 processes)

The local backend provides weaker isolation via subprocess sandboxing with temporary directories — useful for development and testing without Docker overhead.

## The Agent Loop: ReAct with Tool-Use

Vaultrix integrates with Anthropic's Claude API using a ReAct (Reason + Act) loop. The agent receives a goal, reasons about what tools to use, and executes them — all within the permission boundaries:

```
User Goal → Claude reasons → Requests tool use
                                    ↓
                          Permission check → Approved?
                                    ↓              ↓
                                  Yes             No → Error returned to Claude
                                    ↓
                          Sandbox execution → Result fed back to Claude
                                    ↓
                          Repeat until goal complete
```

Built-in tools include:

- **ShellTool** — execute commands (requires `PROCESS:EXECUTE`)
- **FileReadTool** — read files (requires `FILESYSTEM:READ`)
- **FileWriteTool** — write files (requires `FILESYSTEM:WRITE`)
- **PermissionCheckTool** — let the agent query its own permissions (always allowed)

Every tool declares its required permissions. Before execution, each permission is independently verified. The agent can't trick the system by combining innocent-looking operations — each one is checked individually.

If the Anthropic API key isn't configured, the loop gracefully degrades to a dry-run mode that lists available tools and their permissions, useful for testing without API costs.

## VaultHub: Audited Skill Registry

Beyond built-in tools, Vaultrix supports community skills through **VaultHub** — a registry where skills undergo automated security scanning before they can be installed.

The scanner uses Python's `ast` module to perform static analysis on skill code:

```python
# Detected as CRITICAL:
import subprocess          # Dangerous module
eval(user_input)           # Dangerous builtin
os.system("rm -rf /")      # Dangerous attribute

# Detected as WARNING:
import shutil              # Potentially dangerous
```

Skills declare their required permissions in a `skill.yaml` manifest:

```yaml
name: file-organizer
version: 0.1.0
permissions:
  - resource: filesystem
    level: write
    paths: [/workspace/output]
risk_level: medium
entry_point: main.py
```

The CLI provides full skill lifecycle management:

```bash
vaultrix skill init my-skill    # Scaffold a new skill
vaultrix skill check ./my-skill # Run security scanner
vaultrix skill test ./my-skill  # Execute in sandbox
```

## Complete Audit Trail

Every permission check is logged with a timestamp, resource type, permission level, path, and result. This provides a complete audit trail of everything the agent attempted — both allowed and denied:

```python
{
    "timestamp": "2026-03-14T10:30:00Z",
    "resource": "filesystem",
    "level": "write",
    "path": "/workspace/output/report.txt",
    "allowed": true,
    "metadata": {}
}
```

The web dashboard provides real-time visibility into the permission log, letting you monitor agent behavior as it happens.

## Getting Started

```bash
# Clone and install
git clone https://github.com/yourusername/vaultrix.git
cd vaultrix
pip install -e .

# Run the demo
python demo.py

# Start an interactive agent
vaultrix start --interactive

# Or check system requirements
vaultrix check-requirements
```

The demo showcases the permission system, custom permission configuration, and risk level classification — no API key or Docker required.

## What's Next

Vaultrix is currently in Phase 1 (Alpha). Here's the roadmap:

- **Phase 2**: VaultHub registry with automated scanning, manual review, and cryptographic signing
- **Phase 3**: Full human-in-the-loop with approval UI, timeout logic, and notification integrations (Slack, email, webhooks)
- **Phase 4**: Local encryption for agent data, secure memory handling, encrypted communication channels
- **Phase 5**: Penetration testing, security audit, and performance optimization
- **Phase 6**: V1.0 public release with community onboarding

## The Bigger Picture

As AI agents become more capable, the gap between "what an agent can do" and "what an agent should be allowed to do" will only grow. Frameworks that treat security as a first-class concern — not a bolt-on — will be essential.

Vaultrix is our answer: sandbox first, then permissions, then human oversight, then encryption. Each layer builds on the last. No single point of failure.

**Autonomous AI, safely unleashed.**

---

*Vaultrix is open source under the MIT License. We welcome contributions — especially security reviews. If you find a vulnerability, please report it privately.*
