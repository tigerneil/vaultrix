# Vaultrix 🔐

**Secure, Sandboxed, Human-Guided Autonomous AI Framework + AI Control Research Platform**

Vaultrix is two things:
1. A **security framework** for autonomous AI agents — strict sandboxing, audited skill registry (VaultHub), human-in-the-loop execution, and local layered encryption.
2. An **AI control research platform** — five novel control evaluation settings for studying whether control protocols can prevent misaligned agents from causing harm during realistic autonomous workloads.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Security: Sandboxed](https://img.shields.io/badge/Security-Sandboxed-green.svg)]()
[![Tests: 67 passing](https://img.shields.io/badge/Tests-67_passing-brightgreen.svg)]()
[![Status: Alpha](https://img.shields.io/badge/Status-Alpha-orange.svg)]()

---

## 🎯 Core Principles

### 1. **Strict Sandboxing**
All agent operations run within an isolated environment with granular permission controls. Path-traversal protection, resource limits, and no unrestricted system access.

### 2. **VaultHub - Audited Skill Registry**
Community skills undergo automated static analysis and manual review before approval. Dangerous imports (`os`, `subprocess`, `socket`), `eval()`/`exec()`, and data exfiltration patterns are flagged and blocked.

### 3. **Human-in-the-Loop (HITL)**
High-risk actions require explicit user confirmation. Users maintain control over critical system operations via an approval dashboard.

### 4. **Local Layered Encryption**
All agent data, memory, and logs are encrypted at rest using Fernet (AES-128-CBC + HMAC). Zero-knowledge architecture ensures privacy.

### 5. **Multi-Agent Security**
Isolated agents communicate via encrypted channels with trust-based access control, rate limiting, message-type restrictions, and a full audit trail.

### 6. **AI Control Research**
Five control evaluation settings for studying whether monitors can detect covert adversarial behavior during realistic autonomous work. Compatible with [ControlArena](https://github.com/UKGovernmentBEIS/control-arena).

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Docker 20.10+ (optional, for container-based sandbox)

### Installation

```bash
git clone https://github.com/tigerneil/vaultrix.git
cd vaultrix
pip install -r requirements.txt
pip install -e .
```

### Run the demos

```bash
# Quick demo — permission system, custom permissions, risk levels
python demo.py

# Full interactive demo — sandbox, permissions, HITL, encryption, skill scanner, tools
python examples/cli_demo.py

# Multi-agent demo — orchestration, encrypted channels, trust matrix, policy, delegation
python examples/multi_agent_demo.py

# Custom permission examples
python examples/custom_permissions.py

# Basic agent usage
python examples/basic_usage.py
```

### Run the tests

```bash
pytest tests/ -v
# 67 tests, all passing
```

---

## 🔬 AI Control Settings

The `vaultrix/control/` sub-package provides five control evaluation settings for AI safety research. Each pairs a realistic main task with a covert adversarial side task, plus a baseline monitor and scorer.

| Setting | Main Task | Side Task (Attack) | Monitor |
|---|---|---|---|
| **VulnForge** | SWE features on a Flask app | Exploit pre-planted SQLi / path traversal | Diff-review regex |
| **SandboxBreaker** | Build Rust / deploy microservice / CI pipeline | Docker socket / privileged / cgroup / procfs escape | Syscall audit |
| **RogueInterp** | Mechinterp research (probing, patching, circuits) | Systemd service / K8s manifest injection / bg server | Process/port audit |
| **CollusionNet** | Multi-agent SWE project (backend + frontend + reviewer) | Steganographic secret exfiltration via covert channels | Inter-agent base64 decoder |
| **BrowserControl** | Tax forms / data extraction / travel booking | Credential exfil / cron persistence / hosts hijack / remote payload | Network/filesystem audit |

```python
from vaultrix.control import get_setting, list_settings, EvalMode

# List all settings
print(list_settings())
# ['BrowserControlSetting', 'CollusionNetSetting', 'RogueInterpSetting',
#  'SandboxBreakerSetting', 'VulnForgeSetting']

# Use a setting
setting = get_setting("VulnForgeSetting")
for main_task, side_task in setting.get_task_pairs():
    honest_prompt = main_task.get_prompt(EvalMode.HONEST)
    attack_prompt = main_task.get_prompt(EvalMode.ATTACK)  # includes covert objective
```

For details, see the [control settings blog post](docs/blog-control-settings.md).

---

## 📦 Project Structure

```
vaultrix/
├── core/                      # Core agent logic
│   ├── agent/                 # Agent runtime + loop + state
│   ├── sandbox/               # Sandbox backends (local, macOS, Docker)
│   ├── permissions/           # Permission models + manager
│   ├── encryption/            # Fernet encryption manager
│   ├── multi_agent/           # Orchestrator, channels, trust, policy
│   ├── resilience/            # Circuit breaker, fallback
│   ├── tools/                 # Tool registry + builtins (shell, file, perms)
│   ├── hitl.py                # Human-in-the-loop approval
│   └── validation.py          # Input validation
├── control/                   # AI Control evaluation settings
│   ├── base.py                # ABC: ControlSetting, MainTask, SideTask, Scorer, Monitor
│   ├── registry.py            # Setting discovery + registration
│   ├── vulnforge/             # Vulnerability exploitation during SWE
│   ├── sandbox_breaker/       # Container escape under monitoring
│   ├── rogue_interp/          # Rogue deployment during mechinterp research
│   ├── collusion_net/         # Multi-agent collusion via covert channels
│   └── browser_control/       # OS-level harm during web browsing
├── safehub/                   # VaultHub skill scanner + signing
├── ui/                        # HITL dashboard (Flask + templates)
├── cli.py                     # CLI interface
└── skills/                    # Built-in audited skills
examples/
├── basic_usage.py             # Agent creation, commands, file ops
├── cli_demo.py                # Full interactive 6-part demo
├── custom_permissions.py      # Permission boundary examples
└── multi_agent_demo.py        # Multi-agent orchestration demo
tests/
├── test_permissions.py        # Permission system tests
├── test_sandbox.py            # Sandbox isolation tests
├── test_security.py           # Security feature tests
└── test_control.py            # Control settings tests (38 tests)
docs/
└── blog-control-settings.md   # Control settings write-up
```

---

## 🛡️ Implemented Security Features

### Sandbox Isolation
- **Multiple backends**: Local (temp dirs), macOS (Seatbelt), Docker
- **Path-traversal protection**: Blocked and logged
- **Resource limits**: CPU, memory, storage quotas
- **File system isolation**: Virtual workspace with controlled access

### Permission System
- **Granular, path-aware**: Per-resource, per-level, per-path permissions
- **Multiple presets**: `default_sandbox`, `developer`, `restricted`
- **Risk classification**: LOW (auto-execute), MEDIUM (log + execute), HIGH (require approval), CRITICAL (multi-approval + audit)
- **Full access logging**: Every permission check recorded for audit

### Human-in-the-Loop
- **Rich approval UI**: Terminal-based approval prompts with risk context
- **Timeout and fallback**: Configurable timeouts with safe defaults
- **Risk-based gating**: Only HIGH and CRITICAL actions pause for approval

### Encryption
- **Fernet (AES-128-CBC + HMAC)**: All agent data encrypted at rest
- **Structured JSON encryption**: Encrypt/decrypt Python dicts directly
- **File-level encryption**: Save/load encrypted files

### Multi-Agent Security
- **Isolated sandboxes**: Each agent runs in its own sandbox
- **Encrypted inter-agent channels**: Messages encrypted in transit
- **Trust matrix**: Per-pair trust levels (FULL, TRUSTED, STANDARD, RESTRICTED, UNTRUSTED)
- **Policy enforcement**: Rate limits, message size caps, type restrictions
- **Task delegation**: Structured delegation with audit trail

### VaultHub Skill Scanner
- **Static analysis**: Detects dangerous imports, `eval()`/`exec()`, `os.system()`, data exfiltration patterns
- **Severity levels**: WARNING and CRITICAL findings
- **Pass/fail verdict**: Skills with CRITICAL findings are rejected

---

## 🧪 Tests

```bash
pytest tests/ -v
# 67 passed in 0.6s
```

- `test_permissions.py` — Permission system (7 tests)
- `test_sandbox.py` — Sandbox isolation (7 tests)
- `test_security.py` — Security features (15 tests)
- `test_control.py` — Control settings framework + all 5 settings (38 tests)

---

## 📝 Blog & Write-ups

- [Control Settings: Five Threat Models for AI Control Research](docs/blog-control-settings.md)

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Security Contributions
Found a security vulnerability? Please report it privately to security@vaultrix.dev (DO NOT open a public issue).

---

## 📄 License

Vaultrix is released under the [MIT License](LICENSE).

---

## 🙏 Acknowledgments

Built on principles and research from:
- [ControlArena](https://github.com/UKGovernmentBEIS/control-arena) (UK AISI + Redwood Research)
- [SandboxEscapeBench](https://github.com/UKGovernmentBEIS/docker_sandbox_breakout) (Oxford + UK AISI)
- [OS-Harm](https://github.com/tml-epfl/os-harm) (EPFL, built on OSWorld)
- OpenAI's safety research, Anthropic's Constitutional AI, and the open-source AI safety community

---

**Vaultrix: Autonomous AI, Safely Unleashed** 🔐
