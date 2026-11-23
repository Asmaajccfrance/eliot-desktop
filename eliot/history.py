import sqlite3
import threading
from datetime import datetime


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class History:
    def __init__(self, path):
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, created_at TEXT, updated_at TEXT);
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id INTEGER, role TEXT,
                content TEXT, created_at TEXT);
            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, kind TEXT, detail TEXT, status TEXT);
            """
        )
        self._db.commit()

    def _exec(self, sql, args=()):
        with self._lock:
            cur = self._db.execute(sql, args)
            self._db.commit()
            return cur

    def _rows(self, sql, args=()):
        with self._lock:
            return [dict(r) for r in self._db.execute(sql, args).fetchall()]

    def new_conversation(self, title="Nouvelle conversation") -> int:
        return self._exec(
            "INSERT INTO conversations (title, created_at, updated_at) VALUES (?, ?, ?)", (title, _now(), _now())
        ).lastrowid

    def rename(self, cid: int, title: str) -> None:
        self._exec("UPDATE conversations SET title=? WHERE id=?", (title[:80], cid))

    def delete_conversation(self, cid: int) -> None:
        self._exec("DELETE FROM messages WHERE conversation_id=?", (cid,))
        self._exec("DELETE FROM conversations WHERE id=?", (cid,))

    def conversations(self) -> list:
        return self._rows("SELECT * FROM conversations ORDER BY updated_at DESC, id DESC")

    def add_message(self, cid: int, role: str, content: str) -> None:
        self._exec(
            "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (cid, role, content, _now()),
        )
        self._exec("UPDATE conversations SET updated_at=? WHERE id=?", (_now(), cid))

    def messages(self, cid: int, limit: int = 200) -> list:
        rows = self._rows(
            "SELECT role, content, created_at FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT ?",
            (cid, limit),
        )
        return list(reversed(rows))

    def log_action(self, kind: str, detail: str, status: str) -> None:
        self._exec("INSERT INTO actions (created_at, kind, detail, status) VALUES (?, ?, ?, ?)",
                   (_now(), kind, detail[:2000], status))

    def actions(self, limit: int = 50) -> list:
        return self._rows("SELECT * FROM actions ORDER BY id DESC LIMIT ?", (limit,))
