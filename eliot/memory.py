"""Mémoire locale : ce que l'utilisateur demande à ELIOT de retenir."""
import sqlite3
import threading
from datetime import datetime

from .text import simplify


class Memory:
    def __init__(self, path):
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("CREATE TABLE IF NOT EXISTS memories (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT, "
                         "created_at TEXT)")
        self._db.commit()

    def add(self, content: str) -> int:
        content = content.strip().rstrip(".")
        if not content:
            raise ValueError("Rien à retenir.")
        with self._lock:
            cur = self._db.execute("INSERT INTO memories (content, created_at) VALUES (?, ?)",
                                   (content[:500], datetime.now().isoformat(timespec="seconds")))
            self._db.commit()
            return cur.lastrowid

    def all(self) -> list:
        with self._lock:
            return [dict(r) for r in self._db.execute("SELECT * FROM memories ORDER BY id").fetchall()]

    def remove(self, mid: int) -> None:
        with self._lock:
            self._db.execute("DELETE FROM memories WHERE id=?", (mid,))
            self._db.commit()

    def forget(self, query: str) -> int:
        words = [w for w in simplify(query).split() if len(w) > 2]
        removed = 0
        for item in self.all():
            text = simplify(item["content"])
            if words and all(w in text for w in words):
                self.remove(item["id"])
                removed += 1
        return removed

    def as_prompt(self) -> str:
        items = self.all()
        if not items:
            return ""
        return "Ce que tu sais sur l'utilisateur (retenu à sa demande) :\n" + "\n".join(f"- {i['content']}" for i in items[-60:])
