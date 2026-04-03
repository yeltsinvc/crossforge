"""
Task Queue

File-based task queue for managing work between agents.
Each task is a JSON file in the queue directory.
"""

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class TaskStatus(str, Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    id: str
    description: str
    target: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: dict = field(default_factory=dict)


class TaskQueue:
    """File-based task queue using JSON files."""

    def __init__(self, queue_dir: str = "queue"):
        self.queue_dir = Path(queue_dir)
        self.queue_dir.mkdir(parents=True, exist_ok=True)

    def create_task(self, description: str, target: str) -> Task:
        """Create a new task and save it to the queue."""
        task = Task(
            id=f"task_{uuid.uuid4().hex[:8]}",
            description=description,
            target=target,
        )
        self._save_task(task)
        return task

    def get_task(self, task_id: str) -> Task | None:
        """Load a task by ID."""
        task_file = self.queue_dir / f"{task_id}.json"
        if not task_file.exists():
            return None

        with open(task_file) as f:
            data = json.load(f)

        data["status"] = TaskStatus(data["status"])
        return Task(**data)

    def update_status(self, task_id: str, status: TaskStatus) -> None:
        """Update a task's status."""
        task = self.get_task(task_id)
        if task:
            task.status = status
            task.updated_at = datetime.now(timezone.utc).isoformat()
            self._save_task(task)

    def list_tasks(self, status: TaskStatus | None = None) -> list[Task]:
        """List all tasks, optionally filtered by status."""
        tasks = []
        for task_file in self.queue_dir.glob("task_*.json"):
            with open(task_file) as f:
                data = json.load(f)
            data["status"] = TaskStatus(data["status"])
            task = Task(**data)
            if status is None or task.status == status:
                tasks.append(task)
        return sorted(tasks, key=lambda t: t.created_at)

    def _save_task(self, task: Task) -> None:
        """Save task to disk."""
        task_file = self.queue_dir / f"{task.id}.json"
        data = asdict(task)
        data["status"] = task.status.value
        with open(task_file, "w") as f:
            json.dump(data, f, indent=2)
