# Vaultrix v0.2: Multi-Agent Security and Production-Grade Resilience

*From single-agent sandbox to a fleet of isolated, trust-controlled, failure-resilient AI agents*

---

When we first introduced Vaultrix, it solved a clear problem: how to run a single AI agent without giving it the keys to the kingdom. Five layers of defence — sandboxing, permissions, human-in-the-loop, encryption, and skill auditing — meant your agent could act autonomously without acting dangerously.

But the real world doesn't run on single agents. Modern AI workflows involve **teams of agents** — a researcher gathers data, a coder writes solutions, a reviewer checks the work. The moment agents start talking to each other, an entirely new class of security problems emerges:

- Can a compromised agent poison another agent's context?
- Can two agents collude to escalate privileges?
- What happens when the LLM API goes down mid-task?
- How do you trace what happened across a distributed agent fleet?

Vaultrix v0.2 answers all of these. Here's what's new.

## Multi-Agent Security: Every Agent Is an Island

The core idea is simple: **every agent gets its own sandbox, its own permissions, and its own trust boundary.** Agents can only communicate through a mediated, encrypted channel — never directly.

```
                    ┌─────────────────────┐
                    │  Agent Orchestrator  │
                    │  (lifecycle, policy) │
                    └──────────┬──────────┘
                               │
            ┌──────────────────┼──────────────────┐
            │                  │                  │
    ┌───────▼───────┐  ┌──────▼──────┐  ┌───────▼───────┐
    │  Researcher   │  │    Coder    │  │   Reviewer    │
    │  sandbox: own │  │ sandbox: own│  │ sandbox: own  │
    │  perms: read  │  │ perms: dev  │  │ perms: strict │
    └───────┬───────┘  └──────┬──────┘  └───────┬───────┘
            │                 │                  │
    ════════╪═════════════════╪══════════════════╪════════
            │     Secure Channel (encrypted,     │
            │     rate-limited, audited)          │
    ═════════════════════════════════════════════════════
```

### The Orchestrator

The `AgentOrchestrator` manages the full lifecycle of an agent fleet:

```python
with AgentOrchestrator(policy=DEFAULT_MULTI_AGENT_POLICY) as orch:
    orch.spawn_agent("researcher", role="data",
                     permission_set=DEFAULT_SANDBOX_PERMISSIONS)
    orch.spawn_agent("coder", role="code",
                     permission_set=DEVELOPER_PERMISSIONS)
    orch.spawn_agent("reviewer", role="review",
                     permission_set=RESTRICTED_PERMISSIONS)

    # Delegate work
    orch.delegate_task("researcher", "coder",
                       "Build a regression model on Q1 data")

    # Collect results
    results = orch.receive_messages("researcher")
```

Fleet-wide limits are enforced: max 5 concurrent agents by default. Attempting to spawn a 6th raises `OrchestratorError`. Every spawn, termination, and message is recorded in an event log.

### The Trust Matrix

Not all agents are equal. A lead agent might be trusted to send work to anyone, while workers can only communicate with the lead — not with each other:

```
              lead    worker-1   worker-2   worker-3
lead          self    trusted    trusted    trusted
worker-1      std     self       restricted untrusted
worker-2      std     restricted self       untrusted
worker-3      std     untrusted  untrusted  self
```

Trust levels control three things:
1. **Can they communicate at all?** Untrusted agents are completely blocked.
2. **What message types are allowed?** Maybe only `request`/`response`, not `delegate`.
3. **Can they share resources?** Filesystem sharing requires `TRUSTED` level by default.

When `worker-1` tries to message `worker-3` (untrusted), the channel immediately rejects it:

```
> worker-1 → worker-3: send request
✗ Blocked: Communication denied (trust=untrusted)
```

### The Secure Channel

Every inter-agent message flows through a `SecureChannel` that enforces:

- **Encryption**: Payloads are encrypted with Fernet before transit, decrypted only by the recipient
- **Rate limiting**: 60 messages/minute globally, 20 per agent — prevents message flooding
- **Size caps**: Max 64KB per payload — prevents memory exhaustion attacks
- **Type restrictions**: Only allowed message types pass through
- **Audit trail**: Every message attempt (delivered or denied) is logged with timestamps

The channel never stores plaintext. If you inspect the queue, you see:

```python
{"__encrypted__": "gAAAAABptPau..."}
```

Only the recipient can decrypt, using the shared encryption key managed by `EncryptionManager`.

### Structured Task Handoffs

Raw dict payloads between agents are a recipe for miscommunication. We introduced a typed `TaskHandoff` protocol:

```python
handoff = TaskHandoff(
    task="Analyze authentication module",
    from_agent="researcher",
    to_agent="coder",
)
handoff.add_finding(
    title="SQL Injection in login handler",
    severity=Severity.CRITICAL,
    file_path="/app/auth/login.py",
    line_number=47,
    evidence="cursor.execute(f'SELECT * FROM users WHERE id={user_id}')",
    cwe_id="CWE-89",
)
handoff.add_action("Fix with parameterized queries", priority=9)
```

Findings carry severity, CWE IDs, file paths, line numbers, and evidence. Downstream agents get structured context instead of guessing what a blob of JSON means.

## Production Resilience: Lessons from DeepAudit

We studied [DeepAudit](https://github.com/lintsinghua/DeepAudit), an open-source multi-agent code auditing platform that has discovered 49 CVEs across 16 projects. While their security model is minimal (no sandboxing, no permission system), their operational resilience is battle-tested. We adopted four key patterns.

### Circuit Breaker

The problem: Vaultrix's agent loop previously made bare Anthropic API calls. If the API was down or rate-limited, the entire agent crashed.

The fix: A three-state circuit breaker that prevents cascading failures.

```
CLOSED (normal) ──failures exceed threshold──▶ OPEN (rejecting)
       ▲                                            │
       │                              recovery timeout expires
       │                                            ▼
       └────────test call succeeds──────── HALF_OPEN (testing)
```

Separate configs for LLM calls (threshold: 5 failures, 30s recovery) and tool calls (threshold: 3 failures, 60s recovery):

```python
from vaultrix.core.resilience import CircuitBreakerRegistry, LLM_CALL_CONFIG

registry = CircuitBreakerRegistry()
llm_breaker = registry.get_or_create("llm", LLM_CALL_CONFIG)

llm_breaker.before_call()    # raises CircuitOpenError if circuit is open
try:
    result = call_llm(...)
    llm_breaker.record_success()
except Exception:
    llm_breaker.record_failure()  # trips to OPEN after 5 failures
```

### Fallback and Context Reduction

When an LLM call fails due to context overflow, the fallback handler intelligently trims the conversation:

```python
fh = FallbackHandler(strategies=LLM_FALLBACK_STRATEGIES)

# Reduces [system, user1, assistant1, user2, assistant2, user3]
# to      [system, user3]
# Preserving system prompt and last user message
reduced = fh.reduce_context(messages)
```

Tool failures trigger automatic fallback mapping — if `semgrep` fails, fall back to `pattern_match`. The `@with_fallback` decorator wraps any function in a retry loop with automatic strategy selection.

### Structured Agent State

Previously, agent state was a flat list of action history entries. Now it's a full lifecycle model:

```python
state = AgentState(agent_id="researcher-01", role="data")
state.transition(AgentLifecycle.RUNNING)    # validates legal transitions
state.record_tool_use("file_read")
state.record_tokens(1500, 800)              # tracks cost
state.record_error("file not found")

summary = state.get_execution_summary()
# {
#     "duration_seconds": 45.2,
#     "total_tokens": 2300,
#     "unique_tools_used": 1,
#     "error_rate": 0.1,
#     "lifecycle": "running",
# }
```

Seven lifecycle states with validated transitions — you can't go from `COMPLETED` back to `RUNNING`. Token usage accumulates for cost monitoring. Every tool invocation and error is tracked for observability.

### Input Validation and Sanitization

A new defensive layer catches malicious input before it reaches the sandbox:

```python
from vaultrix.core.validation import sanitize_string, sanitize_dict, validate_path

# Strips null bytes and control characters
sanitize_string("hello\x00world\x01")  # → "helloworld"

# Recursive sanitization with depth limits (prevents nested bombs)
sanitize_dict(nested_dict, max_depth=10, max_list_items=100)

# Path traversal prevention
validate_path("../../etc/passwd", ["/workspace"])  # → ValidationError
```

Typed Pydantic schemas validate every tool invocation: command length limits, timeout bounds, file size caps, and a blocklist for dangerous extensions.

## Anti-Hallucination: Mechanical Guardrails

The old system prompt said "don't bypass security controls." That's a suggestion. The new agent loop has mechanical enforcement:

**Minimum tool calls**: The LLM must invoke at least one tool before it can give a final answer. If it tries to respond without gathering evidence, the loop pushes back:

> "You have not used enough tools to support your answer. Please use at least one tool to gather evidence before giving your final response."

**Loop detection**: If the same tool call fails 3 times consecutively, the loop injects a warning asking the LLM to change strategy — preventing infinite retry loops.

**Cancellation support**: Long-running loops can be gracefully cancelled via `loop.cancel()`. The cancellation flag is checked before every LLM call and between tool executions.

## Everything Working Together

Here's how all the pieces fit in a real workflow:

1. The **Orchestrator** spawns three agents, each in its own **sandbox** with its own **permissions**
2. The lead agent delegates tasks through the **Secure Channel** with typed **TaskHandoffs**
3. The **Trust Matrix** blocks unauthorized communication between workers
4. Each agent's **AgentLoop** runs with **anti-hallucination guards** and **circuit breakers**
5. Tool inputs pass through **input validation** before reaching the sandbox
6. The **Fallback Handler** recovers gracefully from API failures
7. **Agent State** tracks lifecycle, tokens, and errors for observability
8. All agent data is **encrypted at rest** with Fernet
9. High-risk actions pause for **human-in-the-loop** approval
10. The **VaultHub scanner** blocks malicious skills before they're ever loaded

Ten layers of protection, each independent.

## Try It Yourself

```bash
git clone https://github.com/tigerneil/vaultrix.git
cd vaultrix && pip install -e .

# Core security demo (6 features)
python examples/cli_demo.py

# Multi-agent security demo (5 features)
python examples/multi_agent_demo.py

# Interactive agent
vaultrix start --interactive
```

No Docker or API keys required. Everything runs locally.

## What's Next

- **Async execution**: Parallel agent dispatch with dependency resolution
- **RAG knowledge base**: Structured vulnerability knowledge injected into agent context
- **Web dashboard**: Real-time trust matrix and message flow visualization
- **Agent specialization**: Typed agent hierarchy (recon, analysis, verification) with role-specific tools

## The Principle

Every new capability in AI agents creates a new attack surface. The answer isn't to limit what agents can do — it's to build security into the infrastructure they run on.

Vaultrix is that infrastructure. Sandbox first. Permissions second. Encrypted channels third. Human oversight fourth. And now: resilience, observability, and multi-agent trust as fifth, sixth, and seventh.

**Autonomous AI, safely unleashed.**

---

*Vaultrix is open source under the MIT License. Contributions welcome — especially security reviews. Found a vulnerability? Report it privately.*
