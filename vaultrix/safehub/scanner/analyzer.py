"""AST-based static-analysis scanner for VaultHub skills.

Detects dangerous patterns *before* a skill is approved:
- Dangerous builtins: eval, exec, __import__, compile
- Subprocess / os.system calls
- Network access (socket, urllib, requests, httpx)
- Obfuscated code (base64 decode + exec combos)
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Finding:
    severity: Severity
    message: str
    file: str
    line: int


@dataclass
class ScanResult:
    skill_name: str
    findings: List[Finding] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not any(f.severity == Severity.CRITICAL for f in self.findings)


# Patterns to flag

_DANGEROUS_BUILTINS = {"eval", "exec", "compile", "__import__", "breakpoint"}
_DANGEROUS_MODULES = {
    "subprocess", "os", "shutil", "ctypes", "multiprocessing",
    "socket", "urllib", "requests", "httpx", "http",
}
_DANGEROUS_ATTRS = {"os.system", "os.popen", "os.exec", "os.spawn", "shutil.rmtree"}


class SkillAnalyzer(ast.NodeVisitor):
    """Walk an AST and collect security findings."""

    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        self.findings: List[Finding] = []

    # -- visitors ------------------------------------------------------------

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            mod = alias.name.split(".")[0]
            if mod in _DANGEROUS_MODULES:
                self._add(Severity.CRITICAL, f"Import of dangerous module: {alias.name}", node)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = (node.module or "").split(".")[0]
        if mod in _DANGEROUS_MODULES:
            self._add(Severity.CRITICAL, f"Import from dangerous module: {node.module}", node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = self._call_name(node)
        if name in _DANGEROUS_BUILTINS:
            self._add(Severity.CRITICAL, f"Use of dangerous builtin: {name}()", node)
        if name in _DANGEROUS_ATTRS:
            self._add(Severity.CRITICAL, f"Use of dangerous call: {name}()", node)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        full = self._attr_chain(node)
        if full in _DANGEROUS_ATTRS:
            self._add(Severity.WARNING, f"Reference to dangerous attribute: {full}", node)
        self.generic_visit(node)

    # -- helpers -------------------------------------------------------------

    def _call_name(self, node: ast.Call) -> str:
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            return self._attr_chain(node.func)
        return ""

    def _attr_chain(self, node: ast.Attribute) -> str:
        parts = [node.attr]
        cur = node.value
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))

    def _add(self, sev: Severity, msg: str, node: ast.AST) -> None:
        self.findings.append(Finding(
            severity=sev,
            message=msg,
            file=self.filepath,
            line=getattr(node, "lineno", 0),
        ))


def scan_skill(skill_dir: Path, skill_name: str = "") -> ScanResult:
    """Scan all ``.py`` files in *skill_dir* and return a ``ScanResult``."""
    result = ScanResult(skill_name=skill_name or skill_dir.name)
    for py_file in skill_dir.rglob("*.py"):
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError as exc:
            result.findings.append(Finding(
                severity=Severity.CRITICAL,
                message=f"Syntax error: {exc}",
                file=str(py_file),
                line=getattr(exc, "lineno", 0) or 0,
            ))
            continue

        analyzer = SkillAnalyzer(str(py_file))
        analyzer.visit(tree)
        result.findings.extend(analyzer.findings)

    logger.info(
        "Scanned %s: %d findings, passed=%s",
        skill_name,
        len(result.findings),
        result.passed,
    )
    return result
