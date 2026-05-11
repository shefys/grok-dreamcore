"""
Memory system — persistent cross-session memory with search.

Built on SQLite with FTS5 for full-text search. Stores episodic
memories, learned preferences, and procedural knowledge. Supports
the Hermes agent's self-improving learning loop.
"""

from __future__ import annotations

import time
import sqlite3
import os
import json
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum


class MemoryType(Enum):
    EPISODIC = "episodic"      # Specific events and conversations.
    PREFERENCE = "preference"   # Learned preferences and patterns.
    PROCEDURAL = "procedural"   # How to do things (skills).
    FACT = "fact"               # Stored facts about the world or owner.
    CONTEXT = "context"         # Contextual state snapshots.


@dataclass
class MemoryEntry:
    """A single memory entry."""
    content: str
    memory_type: MemoryType
    tags: list[str] = field(default_factory=list)
    salience: float = 0.5
    source: str = ""  # Where this memory came from (conversation, automation, etc).
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0

    @property
    def age_hours(self) -> float:
        return (time.time() - self.created_at) / 3600

    @property
    def summary(self) -> str:
        return self.content[:100] + "..." if len(self.content) > 100 else self.content

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "type": self.memory_type.value,
            "tags": self.tags,
            "salience": round(self.salience, 3),
            "source": self.source,
            "age_hours": round(self.age_hours, 1),
            "access_count": self.access_count,
        }


class MemoryStore:
    """SQLite-backed persistent memory store with full-text search."""

    def __init__(self, db_path: str = "./memory_store/emblem_ai.db") -> None:
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._db = sqlite3.connect(db_path)
        self._db.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                tags TEXT DEFAULT '[]',
                salience REAL DEFAULT 0.5,
                source TEXT DEFAULT '',
                created_at REAL NOT NULL,
                last_accessed REAL NOT NULL,
                access_count INTEGER DEFAULT 0
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                content, tags,
                content=memories,
                content_rowid=id
            );

            CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts(rowid, content, tags)
                VALUES (new.id, new.content, new.tags);
            END;

            CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, content, tags)
                VALUES ('delete', old.id, old.content, old.tags);
            END;

            CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, content, tags)
                VALUES ('delete', old.id, old.content, old.tags);
                INSERT INTO memories_fts(rowid, content, tags)
                VALUES (new.id, new.content, new.tags);
            END;

            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_conv_session
                ON conversations(session_id, timestamp);

            CREATE TABLE IF NOT EXISTS nudge_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id INTEGER,
                action TEXT NOT NULL,
                reason TEXT,
                timestamp REAL NOT NULL
            );
        """)
        self._db.commit()

    def store(self, entry: MemoryEntry) -> int:
        """Store a new memory. Returns the memory ID."""
        cursor = self._db.execute(
            """INSERT INTO memories (content, memory_type, tags, salience, source, created_at, last_accessed, access_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.content,
                entry.memory_type.value,
                json.dumps(entry.tags),
                entry.salience,
                entry.source,
                entry.created_at,
                entry.last_accessed,
                entry.access_count,
            ),
        )
        self._db.commit()
        return cursor.lastrowid or 0

    def search(self, query: str, limit: int = 10, memory_type: Optional[MemoryType] = None) -> list[MemoryEntry]:
        """Full-text search across memories."""
        try:
            if memory_type:
                rows = self._db.execute(
                    """SELECT m.* FROM memories m
                       JOIN memories_fts f ON m.id = f.rowid
                       WHERE memories_fts MATCH ? AND m.memory_type = ?
                       ORDER BY rank
                       LIMIT ?""",
                    (query, memory_type.value, limit),
                ).fetchall()
            else:
                rows = self._db.execute(
                    """SELECT m.* FROM memories m
                       JOIN memories_fts f ON m.id = f.rowid
                       WHERE memories_fts MATCH ?
                       ORDER BY rank
                       LIMIT ?""",
                    (query, limit),
                ).fetchall()
        except sqlite3.OperationalError:
            # FTS query syntax error — fall back to LIKE.
            rows = self._db.execute(
                "SELECT * FROM memories WHERE content LIKE ? LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()

        entries = []
        for row in rows:
            entry = self._row_to_entry(row)
            # Mark as accessed.
            self._db.execute(
                "UPDATE memories SET last_accessed = ?, access_count = access_count + 1 WHERE id = ?",
                (time.time(), row["id"]),
            )
            entries.append(entry)
        self._db.commit()
        return entries

    def recent(self, limit: int = 10, memory_type: Optional[MemoryType] = None) -> list[MemoryEntry]:
        """Get most recent memories."""
        if memory_type:
            rows = self._db.execute(
                "SELECT * FROM memories WHERE memory_type = ? ORDER BY created_at DESC LIMIT ?",
                (memory_type.value, limit),
            ).fetchall()
        else:
            rows = self._db.execute(
                "SELECT * FROM memories ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def strongest(self, limit: int = 10) -> list[MemoryEntry]:
        """Get highest-salience memories."""
        rows = self._db.execute(
            "SELECT * FROM memories ORDER BY salience DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def by_tag(self, tag: str, limit: int = 20) -> list[MemoryEntry]:
        """Get memories by tag."""
        rows = self._db.execute(
            "SELECT * FROM memories WHERE tags LIKE ? ORDER BY created_at DESC LIMIT ?",
            (f'%"{tag}"%', limit),
        ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def store_conversation(self, session_id: str, role: str, content: str) -> None:
        """Log a conversation message."""
        self._db.execute(
            "INSERT INTO conversations (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, role, content, time.time()),
        )
        self._db.commit()

    def get_conversation(self, session_id: str, limit: int = 50) -> list[dict[str, str]]:
        """Get conversation history for a session."""
        rows = self._db.execute(
            "SELECT role, content FROM conversations WHERE session_id = ? ORDER BY timestamp LIMIT ?",
            (session_id, limit),
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    def apply_decay(self, rate: float = 0.02) -> int:
        """Decay salience of old memories. Returns count removed."""
        self._db.execute(
            "UPDATE memories SET salience = MAX(0, salience - ?) WHERE salience > 0",
            (rate,),
        )
        cursor = self._db.execute("DELETE FROM memories WHERE salience <= 0.01")
        self._db.commit()
        return cursor.rowcount

    def stats(self) -> dict[str, Any]:
        """Memory store statistics."""
        total = self._db.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        by_type = {}
        for row in self._db.execute(
            "SELECT memory_type, COUNT(*) as c FROM memories GROUP BY memory_type"
        ).fetchall():
            by_type[row["memory_type"]] = row["c"]
        avg_sal = self._db.execute("SELECT AVG(salience) FROM memories").fetchone()[0] or 0
        conversations = self._db.execute("SELECT COUNT(DISTINCT session_id) FROM conversations").fetchone()[0]

        return {
            "total_memories": total,
            "by_type": by_type,
            "avg_salience": round(avg_sal, 3),
            "total_sessions": conversations,
        }

    def close(self) -> None:
        self._db.close()

    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        return MemoryEntry(
            content=row["content"],
            memory_type=MemoryType(row["memory_type"]),
            tags=json.loads(row["tags"]),
            salience=row["salience"],
            source=row["source"],
            created_at=row["created_at"],
            last_accessed=row["last_accessed"],
            access_count=row["access_count"],
        )
