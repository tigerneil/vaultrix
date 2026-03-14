"""Async agent executor for parallel multi-agent workflows.

Provides a task-based execution engine that runs AgentTasks across
multiple VaultrixAgents with dependency resolution, concurrency
limits, and configurable execution modes (sequential, parallel,
adaptive).
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TaskStatus(str, Enum):
    """Lifecycle status of an agent task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionMode(str, Enum):
    """Strategy the executor uses to schedule tasks."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    ADAPTIVE = "adaptive"


# ---------------------------------------------------------------------------
# Task model
# ---------------------------------------------------------------------------

class AgentTask(BaseModel):
    """A unit of work to be dispatched to a VaultrixAgent."""

    task_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    agent_id: str
    task_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    depends_on: List[str] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: Optional[str] = None
    timeout_seconds: int = 600

    model_config = {"use_enum_values": False}


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------

class AgentExecutor:
    """Execute tasks across agents with dependency resolution and concurrency control.

    Parameters
    ----------
    orchestrator : AgentOrchestrator
        The orchestrator that owns the agents.
    mode : ExecutionMode
        Scheduling strategy (default: ADAPTIVE).
    max_parallel : int
        Maximum number of tasks to run concurrently (default: 3).
    """

    def __init__(
        self,
        orchestrator: Any,
        mode: ExecutionMode = ExecutionMode.ADAPTIVE,
        max_parallel: int = 3,
    ) -> None:
        self._orchestrator = orchestrator
        self._mode = mode
        self._max_parallel = max_parallel

        self._tasks: Dict[str, AgentTask] = {}
        self._lock = threading.Lock()
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None

    # -- Public API ---------------------------------------------------------

    def submit(self, task: AgentTask) -> str:
        """Add a single task to the queue. Returns the task_id."""
        with self._lock:
            self._tasks[task.task_id] = task
        logger.info("Submitted task %s (type=%s, agent=%s)", task.task_id, task.task_type, task.agent_id)
        return task.task_id

    def submit_batch(self, tasks: List[AgentTask]) -> List[str]:
        """Add multiple tasks at once. Returns a list of task_ids."""
        ids: List[str] = []
        with self._lock:
            for task in tasks:
                self._tasks[task.task_id] = task
                ids.append(task.task_id)
        logger.info("Submitted batch of %d tasks", len(ids))
        return ids

    def execute_all(self) -> Dict[str, AgentTask]:
        """Run all pending tasks respecting dependencies and concurrency limits.

        Returns a dict mapping task_id to the completed AgentTask (with
        status, result, and error fields populated).
        """
        self._start_time = time.monotonic()

        pending_ids = {
            tid for tid, t in self._tasks.items() if t.status == TaskStatus.PENDING
        }

        if not pending_ids:
            self._end_time = time.monotonic()
            return dict(self._tasks)

        if self._mode == ExecutionMode.SEQUENTIAL:
            self._execute_sequential(pending_ids)
        elif self._mode == ExecutionMode.PARALLEL:
            self._execute_parallel(pending_ids)
        else:
            self._execute_adaptive(pending_ids)

        self._end_time = time.monotonic()
        return dict(self._tasks)

    def get_task(self, task_id: str) -> Optional[AgentTask]:
        """Return a task by id, or None."""
        return self._tasks.get(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task. Returns True if the task was cancelled."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return False
            if task.status != TaskStatus.PENDING:
                return False
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now(timezone.utc).isoformat()
        logger.info("Cancelled task %s", task_id)
        return True

    def get_results(self) -> Dict[str, Any]:
        """Return a dict mapping task_id to result for all completed tasks."""
        return {
            tid: t.result
            for tid, t in self._tasks.items()
            if t.status == TaskStatus.COMPLETED and t.result is not None
        }

    def get_summary(self) -> Dict[str, Any]:
        """Return aggregate statistics about the execution."""
        counts: Dict[str, int] = {}
        for t in self._tasks.values():
            key = t.status.value if isinstance(t.status, TaskStatus) else t.status
            counts[key] = counts.get(key, 0) + 1

        duration: Optional[float] = None
        if self._start_time is not None and self._end_time is not None:
            duration = round(self._end_time - self._start_time, 4)

        return {
            "total_tasks": len(self._tasks),
            "status_counts": counts,
            "execution_mode": self._mode.value if isinstance(self._mode, ExecutionMode) else self._mode,
            "max_parallel": self._max_parallel,
            "total_duration_seconds": duration,
        }

    # -- Execution strategies -----------------------------------------------

    def _execute_sequential(self, pending_ids: set[str]) -> None:
        """Run tasks one-by-one in topological (dependency) order."""
        order = self._topological_sort(pending_ids)
        for tid in order:
            task = self._tasks[tid]
            if task.status == TaskStatus.CANCELLED:
                continue
            if not self._dependencies_met(task):
                self._fail_task(task, "Dependency not met (upstream failure or cancellation)")
                continue
            self._run_task(task)

    def _execute_parallel(self, pending_ids: set[str]) -> None:
        """Run independent tasks concurrently, then process dependents."""
        remaining = set(pending_ids)

        with ThreadPoolExecutor(max_workers=self._max_parallel) as pool:
            while remaining:
                ready = self._get_ready_tasks(remaining)
                if not ready:
                    # All remaining tasks have unmet dependencies; mark failed.
                    for tid in list(remaining):
                        task = self._tasks[tid]
                        self._fail_task(task, "Dependency not met (upstream failure or cancellation)")
                        remaining.discard(tid)
                    break

                futures: Dict[Future, str] = {}
                for tid in ready:
                    task = self._tasks[tid]
                    if task.status == TaskStatus.CANCELLED:
                        remaining.discard(tid)
                        continue
                    future = pool.submit(self._run_task, task)
                    futures[future] = tid

                for future in as_completed(futures):
                    tid = futures[future]
                    remaining.discard(tid)
                    # Propagate any unexpected exception from the future
                    try:
                        future.result()
                    except Exception:
                        pass  # already captured inside _run_task

    def _execute_adaptive(self, pending_ids: set[str]) -> None:
        """Start sequential; switch to parallel when independent tasks exist."""
        remaining = set(pending_ids)

        with ThreadPoolExecutor(max_workers=self._max_parallel) as pool:
            while remaining:
                ready = self._get_ready_tasks(remaining)
                if not ready:
                    for tid in list(remaining):
                        task = self._tasks[tid]
                        self._fail_task(task, "Dependency not met (upstream failure or cancellation)")
                        remaining.discard(tid)
                    break

                if len(ready) == 1:
                    # Only one task is ready -- run sequentially (no thread overhead).
                    tid = next(iter(ready))
                    task = self._tasks[tid]
                    if task.status != TaskStatus.CANCELLED:
                        self._run_task(task)
                    remaining.discard(tid)
                else:
                    # Multiple independent tasks -- fan out in parallel.
                    futures: Dict[Future, str] = {}
                    for tid in ready:
                        task = self._tasks[tid]
                        if task.status == TaskStatus.CANCELLED:
                            remaining.discard(tid)
                            continue
                        future = pool.submit(self._run_task, task)
                        futures[future] = tid

                    for future in as_completed(futures):
                        tid = futures[future]
                        remaining.discard(tid)
                        try:
                            future.result()
                        except Exception:
                            pass

    # -- Task execution -----------------------------------------------------

    def _run_task(self, task: AgentTask) -> None:
        """Execute a single task against its agent, capturing result or error."""
        with self._lock:
            task.status = TaskStatus.RUNNING

        logger.info("Running task %s (type=%s)", task.task_id, task.task_type)

        try:
            result = self._dispatch(task)
            with self._lock:
                task.status = TaskStatus.COMPLETED
                task.result = result if isinstance(result, dict) else {"value": result}
                task.completed_at = datetime.now(timezone.utc).isoformat()
            logger.info("Task %s completed", task.task_id)
        except Exception as exc:
            with self._lock:
                task.status = TaskStatus.FAILED
                task.error = str(exc)
                task.completed_at = datetime.now(timezone.utc).isoformat()
            logger.error("Task %s failed: %s", task.task_id, exc)

    def _dispatch(self, task: AgentTask) -> Any:
        """Look up the agent and call the appropriate method based on task_type.

        Respects the per-task ``timeout_seconds`` using a helper thread.
        """
        agent = self._orchestrator.get_agent(task.agent_id)
        if agent is None:
            raise RuntimeError(f"Agent not found: {task.agent_id}")

        # Run the actual work in a daemon thread so we can enforce a timeout.
        result_holder: Dict[str, Any] = {}
        error_holder: Dict[str, BaseException] = {}

        def _work() -> None:
            try:
                result_holder["value"] = self._call_agent(agent, task)
            except BaseException as exc:
                error_holder["exc"] = exc

        worker = threading.Thread(target=_work, daemon=True)
        worker.start()
        worker.join(timeout=task.timeout_seconds)

        if worker.is_alive():
            raise TimeoutError(
                f"Task {task.task_id} timed out after {task.timeout_seconds}s"
            )
        if "exc" in error_holder:
            raise error_holder["exc"]  # type: ignore[misc]
        return result_holder.get("value")

    def _call_agent(self, agent: Any, task: AgentTask) -> Any:
        """Dispatch to the correct agent / orchestrator method."""
        payload = task.payload
        task_type = task.task_type

        if task_type == "execute_command":
            return agent.execute_command(payload["command"])
        elif task_type == "read_file":
            content = agent.read_file(payload["path"])
            # read_file returns bytes; wrap for JSON-safe result
            return {"content": content.decode("utf-8", errors="replace"), "path": payload["path"]}
        elif task_type == "write_file":
            agent.write_file(payload["path"], payload["content"].encode())
            return {"path": payload["path"], "written": True}
        elif task_type == "delegate":
            msg = self._orchestrator.delegate_task(
                task.agent_id,
                payload["to_agent"],
                payload["task"],
            )
            return {"message_id": msg.id, "to_agent": payload["to_agent"]}
        else:
            raise ValueError(f"Unknown task_type: {task_type}")

    # -- Graph helpers ------------------------------------------------------

    def _topological_sort(self, task_ids: set[str]) -> List[str]:
        """Return task_ids in dependency-first order (Kahn's algorithm)."""
        in_degree: Dict[str, int] = {tid: 0 for tid in task_ids}
        dependents: Dict[str, List[str]] = {tid: [] for tid in task_ids}

        for tid in task_ids:
            task = self._tasks[tid]
            for dep in task.depends_on:
                if dep in task_ids:
                    in_degree[tid] += 1
                    dependents[dep].append(tid)

        queue = [tid for tid in task_ids if in_degree[tid] == 0]
        order: List[str] = []

        while queue:
            tid = queue.pop(0)
            order.append(tid)
            for child in dependents[tid]:
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        # Any task not in order has a cycle or unresolvable dependency.
        for tid in task_ids:
            if tid not in order:
                order.append(tid)

        return order

    def _get_ready_tasks(self, remaining: set[str]) -> set[str]:
        """Return the subset of *remaining* whose dependencies are all satisfied."""
        ready: set[str] = set()
        for tid in remaining:
            task = self._tasks[tid]
            if self._dependencies_met(task):
                ready.add(tid)
        return ready

    def _dependencies_met(self, task: AgentTask) -> bool:
        """Check whether all dependencies of *task* have completed successfully."""
        for dep_id in task.depends_on:
            dep = self._tasks.get(dep_id)
            if dep is None:
                return False
            if dep.status != TaskStatus.COMPLETED:
                return False
        return True

    def _fail_task(self, task: AgentTask, reason: str) -> None:
        with self._lock:
            task.status = TaskStatus.FAILED
            task.error = reason
            task.completed_at = datetime.now(timezone.utc).isoformat()
        logger.warning("Task %s failed: %s", task.task_id, reason)
