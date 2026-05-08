"""
Assistant skills — general personal assistant capabilities.

Handles non-crypto tasks: note-taking, reminders, task tracking,
daily briefings, and research summaries.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum


class TaskPriority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TaskStatus(Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """A tracked task or to-do item."""
    title: str
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.OPEN
    notes: str = ""
    due_at: Optional[float] = None
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    tags: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        import hashlib
        raw = f"{self.title}:{self.created_at}"
        return hashlib.sha256(raw.encode()).hexdigest()[:8]

    @property
    def is_overdue(self) -> bool:
        if self.due_at and self.status == TaskStatus.OPEN:
            return time.time() > self.due_at
        return False

    def complete(self) -> None:
        self.status = TaskStatus.DONE
        self.completed_at = time.time()

    def format_brief(self) -> str:
        status_icon = {"open": "○", "in_progress": "◐", "done": "●", "cancelled": "✕"}
        icon = status_icon.get(self.status.value, "?")
        overdue = " [OVERDUE]" if self.is_overdue else ""
        return f"{icon} [{self.priority.value}] {self.title}{overdue}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "priority": self.priority.value,
            "status": self.status.value,
            "notes": self.notes,
            "tags": self.tags,
            "is_overdue": self.is_overdue,
        }


@dataclass
class Note:
    """A simple note or thought capture."""
    content: str
    tags: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    @property
    def id(self) -> str:
        import hashlib
        return hashlib.sha256(f"{self.content}:{self.created_at}".encode()).hexdigest()[:8]

    @property
    def summary(self) -> str:
        return self.content[:80] + "..." if len(self.content) > 80 else self.content

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "tags": self.tags,
            "created_at": self.created_at,
        }


class TaskManager:
    """Manages tasks, notes, and daily briefings."""

    def __init__(self) -> None:
        self._tasks: list[Task] = []
        self._notes: list[Note] = []

    # ---- Tasks ----

    def add_task(
        self,
        title: str,
        priority: str = "medium",
        notes: str = "",
        tags: Optional[list[str]] = None,
        due_at: Optional[float] = None,
    ) -> Task:
        task = Task(
            title=title,
            priority=TaskPriority(priority),
            notes=notes,
            tags=tags or [],
            due_at=due_at,
        )
        self._tasks.append(task)
        return task

    def complete_task(self, task_id: str) -> Optional[Task]:
        for task in self._tasks:
            if task.id == task_id:
                task.complete()
                return task
        return None

    def get_open_tasks(self, priority: Optional[str] = None) -> list[Task]:
        tasks = [t for t in self._tasks if t.status == TaskStatus.OPEN]
        if priority:
            tasks = [t for t in tasks if t.priority.value == priority]
        return sorted(tasks, key=lambda t: list(TaskPriority).index(t.priority), reverse=True)

    def get_overdue_tasks(self) -> list[Task]:
        return [t for t in self._tasks if t.is_overdue]

    def format_task_list(self) -> str:
        open_tasks = self.get_open_tasks()
        if not open_tasks:
            return "No open tasks."
        lines = ["Open tasks:"]
        for task in open_tasks:
            lines.append(f"  {task.format_brief()}")
        overdue = self.get_overdue_tasks()
        if overdue:
            lines.append(f"\n{len(overdue)} overdue task(s)!")
        return "\n".join(lines)

    # ---- Notes ----

    def add_note(self, content: str, tags: Optional[list[str]] = None) -> Note:
        note = Note(content=content, tags=tags or [])
        self._notes.append(note)
        return note

    def search_notes(self, query: str) -> list[Note]:
        query_lower = query.lower()
        return [n for n in self._notes if query_lower in n.content.lower()]

    def recent_notes(self, limit: int = 5) -> list[Note]:
        return sorted(self._notes, key=lambda n: n.created_at, reverse=True)[:limit]

    # ---- Briefing ----

    def format_daily_briefing(self) -> str:
        """Generate a morning briefing summary."""
        lines = ["Daily briefing:"]

        open_count = len(self.get_open_tasks())
        overdue = self.get_overdue_tasks()
        urgent = [t for t in self.get_open_tasks() if t.priority == TaskPriority.URGENT]

        lines.append(f"\nTasks: {open_count} open")
        if urgent:
            lines.append(f"  Urgent: {len(urgent)}")
            for t in urgent:
                lines.append(f"    - {t.title}")
        if overdue:
            lines.append(f"  Overdue: {len(overdue)}")
            for t in overdue:
                lines.append(f"    - {t.title}")

        recent = self.recent_notes(3)
        if recent:
            lines.append(f"\nRecent notes:")
            for note in recent:
                lines.append(f"  - {note.summary}")

        return "\n".join(lines)

    # ---- Persistence ----

    def serialize(self) -> dict[str, Any]:
        return {
            "tasks": [t.to_dict() for t in self._tasks],
            "notes": [n.to_dict() for n in self._notes],
        }
