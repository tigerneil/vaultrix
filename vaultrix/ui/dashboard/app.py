from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from flask import Flask, jsonify, redirect, render_template, request, url_for

from vaultrix.core.permissions import (
    PermissionLevel,
    PermissionManager,
    PermissionSet,
    ResourceType,
    DEFAULT_SANDBOX_PERMISSIONS,
    DEVELOPER_PERMISSIONS,
    RESTRICTED_PERMISSIONS,
)

app = Flask(
    __name__,
    template_folder=str(Path(__file__).with_name("templates")),
    static_folder=str(Path(__file__).with_name("static")),
)

# Keep a single PermissionManager instance in memory so the access log persists
PM = PermissionManager(DEFAULT_SANDBOX_PERMISSIONS)

PERMISSION_PRESETS: dict[str, PermissionSet] = {
    "default": DEFAULT_SANDBOX_PERMISSIONS,
    "developer": DEVELOPER_PERMISSIONS,
    "restricted": RESTRICTED_PERMISSIONS,
}


def _serialize_pm(pm: PermissionManager) -> Dict[str, Any]:
    summary = pm.get_summary()
    return {
        "summary": summary,
        "access_log": pm.get_access_log(limit=100),
        "permissions": [
            {
                "resource_type": p.resource_type.value if hasattr(p.resource_type, "value") else p.resource_type,
                "level": p.level.value if hasattr(p.level, "value") else p.level,
                "enabled": p.enabled,
                "paths": p.paths,
                "whitelist": p.whitelist,
                "risk_level": p.risk_level.value if hasattr(p.risk_level, "value") else p.risk_level,
            }
            for p in pm.permission_set.permissions
        ],
    }


@app.get("/")
def index() -> str:
    data = _serialize_pm(PM)
    return render_template(
        "index.html",
        data=data,
        current_set=PM.permission_set.name,
        sets=list(PERMISSION_PRESETS.keys()),
    )


@app.post("/set-permission-set")
def set_permission_set():
    name = request.form.get("permission_set", "default")
    preset = PERMISSION_PRESETS.get(name)
    if preset is not None:
        PM.update_permission_set(preset)
    return redirect(url_for("index"))


@app.post("/check")
def check_permission():
    try:
        res = request.form.get("resource", "filesystem")
        lvl = request.form.get("level", "read")
        path = request.form.get("path") or None

        resource = ResourceType(res)
        level = PermissionLevel(lvl)

        allowed = PM.check_permission(resource, level, path=path)
        requires_approval = PM.requires_approval(resource, level)

        message = (
            f"{resource.value}:{level.value} is ALLOWED" if allowed else f"{resource.value}:{level.value} is DENIED"
        )
        return redirect(url_for("index", msg=message, approval=str(requires_approval).lower()))
    except Exception as e:  # broad for simplicity in demo
        return redirect(url_for("index", msg=f"Error: {e}"))


@app.get("/api/status")
def api_status():
    return jsonify(_serialize_pm(PM))


# ── Agent interaction page ─────────────────────────────────────────────────

@app.get("/agent")
def agent_page():
    return render_template("agent.html")


@app.post("/api/agent/run")
def agent_run():
    """Run the agent loop (dry-run if no API key) and return results."""
    from vaultrix.core.sandbox import SandboxManager
    from vaultrix.core.tools.base import ToolRegistry
    from vaultrix.core.tools.builtins import (
        FileReadTool,
        FileWriteTool,
        PermissionCheckTool,
        ShellTool,
    )
    from vaultrix.core.agent.loop import AgentLoop

    body = request.get_json(silent=True) or {}
    goal = body.get("goal", "")
    if not goal:
        return jsonify({"error": "No goal provided"}), 400

    sm = SandboxManager()
    sm.create_sandbox()

    registry = ToolRegistry()
    registry.register(ShellTool(sm))
    registry.register(FileReadTool(sm))
    registry.register(FileWriteTool(sm))
    registry.register(PermissionCheckTool(PM))

    loop = AgentLoop(PM, registry)
    try:
        result = loop.run(goal)
    finally:
        sm.destroy_sandbox()

    return jsonify({
        "result": result,
        "steps": [
            {
                "role": s.role,
                "content": s.content,
                "tool_name": s.tool_name,
                "tool_result": s.tool_result,
                "timestamp": s.timestamp,
            }
            for s in loop.history
        ],
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)
