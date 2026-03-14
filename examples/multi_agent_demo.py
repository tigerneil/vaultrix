#!/usr/bin/env python3
"""
Vaultrix Multi-Agent Security Demo
===================================
Demonstrates secure multi-agent orchestration:

1. Spawn isolated agents with separate sandboxes
2. Secure encrypted communication via channel
3. Trust-based access control
4. Policy enforcement (rate limits, message types, size)
5. Task delegation between agents
6. Global audit trail

Run:
    python examples/multi_agent_demo.py
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console()
PAUSE = 0.3


def banner(title: str, sub: str = "") -> None:
    body = f"[bold cyan]{title}[/bold cyan]"
    if sub:
        body += f"\n[dim]{sub}[/dim]"
    console.print()
    console.print(Panel.fit(body, border_style="cyan", padding=(1, 4)))
    console.print()


def step(msg: str) -> None:
    console.print(f"  [bold green]>[/bold green] {msg}")
    time.sleep(PAUSE)


def substep(msg: str) -> None:
    console.print(f"    {msg}")


def ok(msg: str) -> None:
    console.print(f"  [bold green]OK[/bold green] {msg}")


def fail(msg: str) -> None:
    console.print(f"  [bold red]x[/bold red] {msg}")


def wait() -> None:
    try:
        console.input("\n  [dim]Press Enter to continue ...[/dim] ")
    except EOFError:
        console.print()
        time.sleep(PAUSE)


# ── Demos ──────────────────────────────────────────────────────────────────


def demo_orchestrator() -> None:
    """1. Spawn multiple agents with isolated sandboxes."""
    banner(
        "1 / 5  Agent Orchestration",
        "Spawn isolated agents, each with its own sandbox and permissions.",
    )

    from vaultrix.core.multi_agent import AgentOrchestrator, DEFAULT_MULTI_AGENT_POLICY
    from vaultrix.core.permissions import DEFAULT_SANDBOX_PERMISSIONS, DEVELOPER_PERMISSIONS

    with AgentOrchestrator(policy=DEFAULT_MULTI_AGENT_POLICY) as orch:
        step(f"Policy: [bold]{orch.policy.name}[/bold]  max_agents={orch.policy.max_agents}")

        step("Spawning agent: [cyan]researcher[/cyan] (default perms)")
        orch.spawn_agent("researcher", role="researcher")

        step("Spawning agent: [cyan]coder[/cyan] (developer perms)")
        orch.spawn_agent("coder", role="coder", permission_set=DEVELOPER_PERMISSIONS)

        step("Spawning agent: [cyan]reviewer[/cyan] (default perms)")
        orch.spawn_agent("reviewer", role="reviewer")

        ok(f"{len(orch._agents)} agents running in separate sandboxes")

        # Show status
        status = orch.get_status()
        table = Table(title="Agent Fleet", box=box.SIMPLE)
        table.add_column("Agent ID", style="cyan")
        table.add_column("Role")
        table.add_column("Sandbox", justify="center")
        for aid, info in status["agents"].items():
            table.add_row(aid, info["role"], f"[green]{info['sandbox_status']}[/green]")
        console.print(table)

        # Try exceeding limit
        step(f"Attempting to spawn beyond limit ({orch.policy.max_agents}) ...")
        try:
            for i in range(10):
                orch.spawn_agent(f"extra-{i}", role="extra")
        except Exception as e:
            ok(f"Blocked: {e}")

    wait()


def demo_secure_channel() -> None:
    """2. Encrypted inter-agent messaging."""
    banner(
        "2 / 5  Secure Channel Communication",
        "Messages are encrypted, policy-checked, and audited.",
    )

    from vaultrix.core.multi_agent import (
        AgentOrchestrator, MessageType, DEFAULT_MULTI_AGENT_POLICY,
    )
    from vaultrix.core.encryption.manager import EncryptionManager

    with tempfile.TemporaryDirectory(prefix="vaultrix_ma_") as tmpdir:
        enc = EncryptionManager(key_dir=Path(tmpdir))

        with AgentOrchestrator(policy=DEFAULT_MULTI_AGENT_POLICY, encryption=enc) as orch:
            orch.spawn_agent("alice", role="researcher")
            orch.spawn_agent("bob", role="coder")

            step("Alice sends encrypted request to Bob ...")
            msg = orch.send_message(
                from_agent="alice",
                to_agent="bob",
                message_type=MessageType.REQUEST,
                payload={"task": "Write a sorting algorithm", "priority": "high"},
            )
            substep(f"Message ID: {msg.id}")
            substep(f"Encrypted: [green]{msg.encrypted}[/green]")

            step("Bob receives and decrypts ...")
            msgs = orch.receive_messages("bob")
            ok(f"Bob received {len(msgs)} message(s)")
            for m in msgs:
                substep(f"Type: {m.message_type.value}  Payload: {m.payload}")

            # Show audit trail
            step("Channel audit trail:")
            table = Table(box=box.SIMPLE, show_header=True)
            table.add_column("From")
            table.add_column("To")
            table.add_column("Type")
            table.add_column("Verdict", justify="center")
            for entry in orch.channel.get_audit_log():
                v_color = "green" if entry["verdict"] == "DELIVERED" else "red"
                table.add_row(
                    entry["from"], entry["to"], entry["type"],
                    f"[{v_color}]{entry['verdict']}[/{v_color}]",
                )
            console.print(table)

    wait()


def demo_trust_matrix() -> None:
    """3. Trust-based access control."""
    banner(
        "3 / 5  Trust Matrix & Access Control",
        "Agents have trust levels that control communication and resource sharing.",
    )

    from vaultrix.core.multi_agent import (
        AgentOrchestrator, MessageType, TrustLevel,
    )
    from vaultrix.core.multi_agent.policy import (
        CommunicationPolicy, AgentTrustRule, ResourceSharingRule,
    )

    policy = CommunicationPolicy(
        name="trust_demo",
        max_agents=5,
        trust_rules=[
            AgentTrustRule(from_agent="lead", to_agent="*", trust_level=TrustLevel.TRUSTED),
            AgentTrustRule(from_agent="*", to_agent="lead", trust_level=TrustLevel.STANDARD),
            AgentTrustRule(from_agent="worker-1", to_agent="worker-2", trust_level=TrustLevel.RESTRICTED),
            AgentTrustRule(from_agent="worker-2", to_agent="worker-1", trust_level=TrustLevel.RESTRICTED),
            # worker -> worker-3: no rule = untrusted
        ],
        resource_sharing=[
            ResourceSharingRule(
                resource_type="filesystem",
                sharing_allowed=True,
                require_trust_level=TrustLevel.TRUSTED,
                allowed_paths=["/workspace/shared"],
            ),
        ],
    )

    with AgentOrchestrator(policy=policy) as orch:
        for aid in ["lead", "worker-1", "worker-2", "worker-3"]:
            orch.spawn_agent(aid, role="lead" if aid == "lead" else "worker")

        step("Trust matrix:")
        matrix = orch.get_trust_matrix()
        table = Table(title="Trust Levels", box=box.ROUNDED)
        table.add_column("", style="cyan bold")
        for aid in matrix:
            table.add_column(aid, justify="center")
        for a, row in matrix.items():
            cells = []
            for b, lvl in row.items():
                color = {
                    "full": "bold green", "trusted": "green",
                    "standard": "cyan", "restricted": "yellow",
                    "untrusted": "red", "self": "dim",
                }.get(lvl, "white")
                cells.append(f"[{color}]{lvl}[/{color}]")
            table.add_row(a, *cells)
        console.print(table)

        # Test communication
        console.print()
        step("lead -> worker-1 (trusted): send request ...")
        try:
            orch.send_message("lead", "worker-1", MessageType.REQUEST, {"cmd": "analyze"})
            ok("Delivered")
        except Exception as e:
            fail(str(e))

        step("worker-1 -> worker-3 (untrusted): send request ...")
        try:
            orch.send_message("worker-1", "worker-3", MessageType.REQUEST, {"cmd": "help"})
            ok("Delivered")
        except Exception as e:
            ok(f"Blocked: {e}")

        # Resource sharing
        console.print()
        step("Can lead share filesystem with worker-1?")
        can = policy.can_share_resource("lead", "worker-1", "filesystem")
        result = "[green]YES[/green]" if can else "[red]NO[/red]"
        substep(f"Result: {result}  (lead is TRUSTED)")

        step("Can worker-1 share filesystem with worker-2?")
        can = policy.can_share_resource("worker-1", "worker-2", "filesystem")
        result = "[green]YES[/green]" if can else "[red]NO[/red]"
        substep(f"Result: {result}  (worker-1 is only RESTRICTED to worker-2)")

    wait()


def demo_policy_enforcement() -> None:
    """4. Rate limits, message size, and type enforcement."""
    banner(
        "4 / 5  Policy Enforcement",
        "Rate limits, message size caps, and message type restrictions.",
    )

    from vaultrix.core.multi_agent import AgentOrchestrator, MessageType
    from vaultrix.core.multi_agent.policy import (
        CommunicationPolicy, AgentTrustRule, TrustLevel,
    )

    policy = CommunicationPolicy(
        name="strict_test",
        max_agents=5,
        max_messages_per_minute=5,
        max_messages_per_agent_per_minute=3,
        trust_rules=[
            AgentTrustRule(
                from_agent="*", to_agent="*",
                trust_level=TrustLevel.RESTRICTED,
                allowed_message_types=["request", "response"],
                max_message_size=256,
                require_encryption=False,
            ),
        ],
    )

    with AgentOrchestrator(policy=policy) as orch:
        orch.spawn_agent("sender", role="sender")
        orch.spawn_agent("receiver", role="receiver")

        # Rate limit test
        step(f"Sending messages (per-agent limit: {policy.max_messages_per_agent_per_minute}/min) ...")
        for i in range(5):
            try:
                orch.send_message("sender", "receiver", MessageType.REQUEST, {"i": i})
                substep(f"Message {i+1}: [green]delivered[/green]")
            except Exception as e:
                substep(f"Message {i+1}: [red]blocked[/red] - {e}")

        # Size limit test
        console.print()
        step("Sending oversized message (>256 bytes) ...")
        try:
            orch.send_message("sender", "receiver", MessageType.REQUEST, {
                "data": "x" * 500,
            })
            fail("Should have been blocked!")
        except Exception as e:
            ok(f"Blocked: {e}")

        # Type restriction test
        console.print()
        step("Sending disallowed message type (DELEGATE) ...")
        try:
            orch.send_message("sender", "receiver", MessageType.DELEGATE, {"task": "test"})
            fail("Should have been blocked!")
        except Exception as e:
            ok(f"Blocked: {e}")

    wait()


def demo_task_delegation() -> None:
    """5. Cross-agent task delegation."""
    banner(
        "5 / 5  Task Delegation",
        "A lead agent delegates work to specialists, collects results.",
    )

    from vaultrix.core.multi_agent import AgentOrchestrator, MessageType
    from vaultrix.core.multi_agent.policy import (
        CommunicationPolicy, AgentTrustRule, TrustLevel,
    )

    policy = CommunicationPolicy(
        name="delegation_demo",
        max_agents=5,
        trust_rules=[
            AgentTrustRule(
                from_agent="*", to_agent="*",
                trust_level=TrustLevel.TRUSTED,
                allowed_message_types=["request", "response", "delegate", "result", "status"],
                require_encryption=False,
            ),
        ],
    )

    with AgentOrchestrator(policy=policy) as orch:
        orch.spawn_agent("lead", role="lead")
        orch.spawn_agent("data-agent", role="data")
        orch.spawn_agent("code-agent", role="coder")

        step("Lead delegates 'fetch dataset' to data-agent ...")
        orch.delegate_task("lead", "data-agent", "Fetch sales dataset for Q1 2026")

        step("Lead delegates 'build model' to code-agent ...")
        orch.delegate_task("lead", "code-agent", "Build regression model on Q1 data")

        # Simulate responses
        step("data-agent sends result back to lead ...")
        orch.send_message("data-agent", "lead", MessageType.RESULT, {
            "status": "complete",
            "rows": 15000,
            "path": "/workspace/shared/q1_sales.csv",
        })

        step("code-agent sends result back to lead ...")
        orch.send_message("code-agent", "lead", MessageType.RESULT, {
            "status": "complete",
            "model": "linear_regression",
            "accuracy": 0.94,
        })

        # Lead collects results
        step("Lead collects all results ...")
        results = orch.receive_messages("lead")
        ok(f"Received {len(results)} results")
        for r in results:
            substep(f"From [cyan]{r.from_agent}[/cyan]: {r.payload}")

        # Show events
        console.print()
        step(f"Orchestrator events: {len(orch.events)}")
        table = Table(box=box.SIMPLE, show_header=True)
        table.add_column("Event", style="cyan")
        table.add_column("Details")
        for ev in orch.events[-8:]:
            table.add_row(ev["event"], str(ev["data"]))
        console.print(table)

    wait()


# ── Main ───────────────────────────────────────────────────────────────────


def main() -> None:
    console.print(
        Panel.fit(
            "[bold white on blue]  VAULTRIX MULTI-AGENT  [/bold white on blue]\n\n"
            "[bold]Secure Multi-Agent Orchestration Demo[/bold]\n\n"
            "Demonstrates isolated agents, encrypted communication,\n"
            "trust-based access control, and policy enforcement.\n\n"
            "[dim]5 demos  |  ~2 minutes  |  fully local[/dim]",
            border_style="blue",
            padding=(1, 6),
        )
    )

    wait()

    demos = [
        demo_orchestrator,
        demo_secure_channel,
        demo_trust_matrix,
        demo_policy_enforcement,
        demo_task_delegation,
    ]

    for fn in demos:
        try:
            fn()
        except KeyboardInterrupt:
            console.print("\n[dim]Skipped.[/dim]")
        except Exception as e:
            console.print(f"\n[red]Error in {fn.__name__}: {e}[/red]")
            import traceback
            traceback.print_exc()

    console.print()
    console.print(
        Panel.fit(
            "[bold green]Multi-Agent Demo Complete![/bold green]\n\n"
            "You've seen Vaultrix multi-agent security:\n\n"
            "  [cyan]1.[/cyan] Agent orchestration with isolated sandboxes\n"
            "  [cyan]2.[/cyan] Encrypted inter-agent communication\n"
            "  [cyan]3.[/cyan] Trust matrix controlling access\n"
            "  [cyan]4.[/cyan] Rate limits, size caps, type restrictions\n"
            "  [cyan]5.[/cyan] Secure task delegation between agents\n\n"
            "[dim]Run: python examples/multi_agent_demo.py[/dim]",
            title="Vaultrix",
            border_style="green",
            padding=(1, 4),
        )
    )
    console.print()


if __name__ == "__main__":
    main()
