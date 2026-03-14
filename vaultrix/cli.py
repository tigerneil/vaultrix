"""Command-line interface for Vaultrix."""

import logging
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich import print as rprint

from vaultrix import __version__
from vaultrix.core.agent import VaultrixAgent
from vaultrix.core.sandbox import SandboxConfig
from vaultrix.core.permissions import (
    PermissionSet,
    DEFAULT_SANDBOX_PERMISSIONS,
    DEVELOPER_PERMISSIONS,
    RESTRICTED_PERMISSIONS,
)
from vaultrix.core.config import ConfigManager


console = Console()
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version=__version__)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def cli(verbose: bool):
    """Vaultrix - Secure, Sandboxed, Human-Guided Autonomous AI Framework"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


@cli.command()
@click.option(
    "--permission-set",
    type=click.Choice(["default", "developer", "restricted"]),
    default="default",
    help="Permission set to use"
)
@click.option("--interactive", "-i", is_flag=True, help="Start in interactive mode")
def start(permission_set: str, interactive: bool):
    """Start a Vaultrix agent."""
    console.print(Panel.fit(
        "[bold cyan]Vaultrix Agent Starting[/bold cyan]\n"
        f"Permission Set: {permission_set}\n"
        f"Interactive: {interactive}",
        title="🔐 Vaultrix"
    ))

    # Select permission set
    perm_sets = {
        "default": DEFAULT_SANDBOX_PERMISSIONS,
        "developer": DEVELOPER_PERMISSIONS,
        "restricted": RESTRICTED_PERMISSIONS,
    }
    perm = perm_sets[permission_set]

    try:
        with VaultrixAgent(permission_set=perm) as agent:
            console.print("[green]✓[/green] Agent started successfully")
            console.print(f"[dim]Agent ID: {agent.agent_id}[/dim]")

            if interactive:
                interactive_mode(agent)
            else:
                # Show agent status
                show_status(agent)
                console.print("\n[dim]Use --interactive / -i to enter interactive mode.[/dim]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}", style="bold red")
        sys.exit(1)


def interactive_mode(agent: VaultrixAgent):
    """Run agent in interactive mode."""
    import sys
    if not sys.stdin.isatty():
        console.print("[yellow]No interactive terminal detected.[/yellow]")
        console.print("[dim]Interactive mode requires a real terminal (not piped stdin).[/dim]")
        console.print("[dim]Try running directly in your terminal: vaultrix start -i[/dim]")
        show_status(agent)
        return

    console.print("\n[bold]Interactive Mode[/bold]")
    console.print("[dim]Type 'help' for commands, 'exit' to quit[/dim]\n")

    while True:
        try:
            command = console.input("[bold cyan]vaultrix>[/bold cyan] ")
            command = command.strip()

            if not command:
                continue

            if command in ["exit", "quit"]:
                break

            if command == "help":
                show_help()
                continue

            if command == "status":
                show_status(agent)
                continue

            if command.startswith("exec "):
                cmd = command[5:]
                result = agent.execute_command(cmd)
                console.print(result["stdout"])
                if result["exit_code"] != 0:
                    console.print(f"[red]Exit code: {result['exit_code']}[/red]")
                continue

            if command == "logs":
                show_logs(agent)
                continue

            console.print("[yellow]Unknown command. Type 'help' for available commands.[/yellow]")

        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Exiting...[/dim]")
            break
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")


def show_help():
    """Show help information."""
    help_text = """
[bold]Available Commands:[/bold]

  [cyan]help[/cyan]              Show this help message
  [cyan]status[/cyan]            Show agent status
  [cyan]logs[/cyan]              Show agent logs
  [cyan]exec <command>[/cyan]   Execute a command in the sandbox
  [cyan]exit[/cyan]              Exit interactive mode

[bold]Examples:[/bold]

  exec ls -la
  exec python --version
  exec cat /workspace/test.txt
"""
    console.print(help_text)


def show_status(agent: VaultrixAgent):
    """Show agent status."""
    status = agent.get_status()

    table = Table(title="Agent Status")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Agent ID", status["agent_id"])
    table.add_row("Uptime", f"{status['uptime_seconds']:.1f}s")
    table.add_row("Sandbox Status", status["sandbox"]["status"])
    table.add_row("Actions Executed", str(status["actions_executed"]))
    table.add_row("Permission Set", status["permissions"]["permission_set"])
    table.add_row("Denied Attempts", str(status["permissions"]["denied_attempts"]))

    console.print(table)


def show_logs(agent: VaultrixAgent):
    """Show agent logs."""
    logs = agent.get_logs()

    console.print("\n[bold]Recent Sandbox Logs:[/bold]")
    for line in logs["sandbox_logs"][-10:]:
        if line.strip():
            console.print(f"  {line}")

    console.print("\n[bold]Recent Actions:[/bold]")
    for action in logs["action_history"][-5:]:
        console.print(f"  [{action['timestamp']}] {action['action_type']}")


@cli.command()
def info():
    """Show Vaultrix information."""
    info_panel = f"""
[bold cyan]Vaultrix[/bold cyan] - Secure Autonomous AI Framework

[bold]Version:[/bold] {__version__}
[bold]Status:[/bold] Alpha

[bold]Security Features:[/bold]
  • Strict Sandboxing (Docker-based isolation)
  • Granular Permission Control
  • Human-in-the-Loop for high-risk actions
  • Local Layered Encryption
  • Audited Skill Registry (VaultHub)

[bold]Documentation:[/bold] https://docs.vaultrix.dev
[bold]Repository:[/bold] https://github.com/tigerneil/vaultrix
"""
    console.print(Panel(info_panel, title="🔐 Information", border_style="cyan"))


@cli.command()
def check_requirements():
    """Check if system requirements are met."""
    console.print("[bold]Checking System Requirements...[/bold]\n")

    requirements = []

    # Check Docker
    try:
        import docker
        client = docker.from_env()
        client.ping()
        requirements.append(("Docker", "✓", "green"))
    except Exception as e:
        requirements.append(("Docker", f"✗ {e}", "red"))

    # Check Python version
    import sys
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    if sys.version_info >= (3, 10):
        requirements.append(("Python", f"✓ {py_version}", "green"))
    else:
        requirements.append(("Python", f"✗ {py_version} (need 3.10+)", "red"))

    # Check dependencies
    try:
        import anthropic
        requirements.append(("Anthropic SDK", "✓", "green"))
    except ImportError:
        requirements.append(("Anthropic SDK", "✗ Not installed", "yellow"))

    # Display results
    table = Table(title="System Requirements")
    table.add_column("Component", style="cyan")
    table.add_column("Status")

    for name, status, color in requirements:
        table.add_row(name, f"[{color}]{status}[/{color}]")

    console.print(table)


@cli.group()
def config():
    """Manage Vaultrix configuration."""
    pass


@config.command(name="show")
def config_show():
    """Show current configuration."""
    mgr = ConfigManager()
    cfg = mgr.load()

    table = Table(title="Vaultrix Configuration")
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")

    # Group display using sections
    sections = {
        "LLM": [
            ("llm.provider", cfg.llm_provider),
            ("llm.model", cfg.llm_model),
            ("llm.api_key", "****" if cfg.llm_api_key else "[dim]not set[/dim]"),
        ],
        "Permissions": [
            ("default_permission_set", cfg.default_permission_set),
        ],
        "Sandbox": [
            ("sandbox.backend", cfg.sandbox_backend),
            ("sandbox.timeout", str(cfg.sandbox_timeout)),
            ("sandbox.memory_limit", cfg.sandbox_memory_limit),
        ],
        "Human-in-the-Loop": [
            ("hitl.auto_approve_low_risk", str(cfg.hitl_auto_approve_low_risk)),
            ("hitl.timeout", str(cfg.hitl_timeout)),
        ],
        "Encryption": [
            ("encryption.key_dir", cfg.encryption_key_dir or "[dim]~/.vaultrix[/dim]"),
        ],
        "Multi-Agent": [
            ("multi_agent.max_agents", str(cfg.multi_agent_max_agents)),
            ("multi_agent.require_encryption", str(cfg.multi_agent_require_encryption)),
        ],
        "Logging": [
            ("log_level", cfg.log_level),
        ],
    }

    for section, fields in sections.items():
        table.add_row(f"[bold]{section}[/bold]", "")
        for key, value in fields:
            table.add_row(f"  {key}", value)

    console.print(table)

    config_file = mgr.config_path
    if config_file.exists():
        console.print(f"\n[dim]Config file: {config_file}[/dim]")
    else:
        console.print(f"\n[dim]No config file found (using defaults). Path: {config_file}[/dim]")


@config.command(name="set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str):
    """Set a configuration value (e.g. vaultrix config set llm.model gpt-4)."""
    mgr = ConfigManager()
    try:
        mgr.set(key, value)
        console.print(f"[green]Set[/green] [cyan]{key}[/cyan] = {value}")
    except (KeyError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@config.command(name="reset")
@click.confirmation_option(prompt="Reset all configuration to defaults?")
def config_reset():
    """Reset configuration to defaults."""
    mgr = ConfigManager()
    mgr.reset()
    console.print("[green]Configuration reset to defaults.[/green]")


@cli.group()
def skill():
    """Manage VaultHub skills."""
    pass


@skill.command(name="list")
def skill_list():
    """List installed skills."""
    console.print("[yellow]VaultHub integration coming in Phase 2![/yellow]")


@skill.command(name="install")
@click.argument("skill_name")
def skill_install(skill_name: str):
    """Install a skill from VaultHub."""
    console.print(f"[yellow]Installing {skill_name}...[/yellow]")
    console.print("[yellow]VaultHub integration coming in Phase 2![/yellow]")


@skill.command(name="init")
@click.argument("name")
def skill_init(name: str):
    """Scaffold a new skill directory with skill.yaml."""
    from pathlib import Path

    skill_dir = Path(name)
    skill_dir.mkdir(exist_ok=True)
    manifest = skill_dir / "skill.yaml"
    if not manifest.exists():
        manifest.write_text(
            f"name: {name}\nversion: 0.1.0\ndescription: ''\nauthor: ''\n"
            f"license: MIT\npermissions:\n  required:\n    - resource: filesystem\n"
            f"      level: read\n      paths: [/workspace]\nrisk_level: low\n"
            f"entry_point: main.py\ntags: []\n"
        )
    entry = skill_dir / "main.py"
    if not entry.exists():
        entry.write_text('"""Skill entry point."""\n\nprint("Hello from ' + name + '!")\n')
    console.print(f"[green]\u2713[/green] Scaffolded skill at [cyan]{skill_dir}[/cyan]")


@skill.command(name="check")
@click.argument("skill_dir")
def skill_check(skill_dir: str):
    """Run the security scanner on a skill directory."""
    from pathlib import Path
    from vaultrix.safehub.scanner.analyzer import scan_skill

    result = scan_skill(Path(skill_dir))
    if not result.findings:
        console.print(f"[green]\u2713[/green] No findings for [cyan]{result.skill_name}[/cyan]")
    else:
        for f in result.findings:
            style = "red" if f.severity.value == "critical" else "yellow"
            console.print(f"[{style}]{f.severity.value.upper()}[/{style}] {f.file}:{f.line} — {f.message}")
    status = "[green]PASSED[/green]" if result.passed else "[red]FAILED[/red]"
    console.print(f"\nScan result: {status}")


@skill.command(name="sign")
@click.argument("skill_dir")
@click.option("--key-id", default=None, help="Key ID to sign with (default: first available)")
def skill_sign(skill_dir: str, key_id: Optional[str]):
    """Sign a skill directory with HMAC-SHA256."""
    from vaultrix.safehub.signing import SigningManager

    mgr = SigningManager()

    # Ensure at least one keypair exists.
    if not mgr.list_keys():
        console.print("[dim]No keypairs found — generating one now...[/dim]")
        mgr.generate_keypair()

    try:
        key = mgr.load_keypair(key_id)
        sig = mgr.sign_skill(Path(skill_dir), key)
        console.print(f"[green]\u2713[/green] Signed [cyan]{sig.skill_name}[/cyan] v{sig.skill_version}")
        console.print(f"  Key:  {sig.signer_key_id}")
        console.print(f"  Hash: {sig.content_hash[:16]}...")
    except Exception as e:
        console.print(f"[red]Error signing skill:[/red] {e}")
        sys.exit(1)


@skill.command(name="verify")
@click.argument("skill_dir")
def skill_verify(skill_dir: str):
    """Verify the signature of a skill directory."""
    from vaultrix.safehub.signing import SigningManager

    mgr = SigningManager()
    ok = mgr.verify_skill(Path(skill_dir))
    if ok:
        console.print(f"[green]\u2713[/green] Signature valid for [cyan]{skill_dir}[/cyan]")
    else:
        console.print(f"[red]\u2717[/red] Signature verification FAILED for [cyan]{skill_dir}[/cyan]")
        sys.exit(1)


@skill.command(name="test")
@click.argument("skill_dir")
def skill_test(skill_dir: str):
    """Load and run a skill in the local sandbox."""
    from pathlib import Path
    from vaultrix.core.sandbox import SandboxManager
    from vaultrix.core.permissions import PermissionManager, DEFAULT_SANDBOX_PERMISSIONS
    from vaultrix.safehub.runner import SkillRunner

    sm = SandboxManager()
    pm = PermissionManager(DEFAULT_SANDBOX_PERMISSIONS)
    runner = SkillRunner(sm, pm)
    sm.create_sandbox()
    try:
        result = runner.run(Path(skill_dir))
        if result["success"]:
            console.print(f"[green]\u2713[/green] Skill completed successfully")
            if result.get("stdout"):
                console.print(result["stdout"])
        else:
            console.print(f"[red]\u2717[/red] Skill failed: {result.get('error', '')}")
            if result.get("stderr"):
                console.print(result["stderr"])
    finally:
        sm.destroy_sandbox()


def main():
    """Main entry point."""
    try:
        cli()
    except Exception as e:
        console.print(f"[red]Fatal error:[/red] {e}", style="bold red")
        sys.exit(1)


if __name__ == "__main__":
    main()
