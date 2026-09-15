"""Persistência do servidor: contas de usuário e a fila de mensagens offline.

O servidor nunca vê o conteúdo real de uma mensagem entre dois usuários: o que
fica guardado em offline_messages é o "peer_frame" opaco recebido do
remetente, que só o destinatário consegue abrir (seção 8.4).
"""
import json
import sqlite3
import threading
import time


class Database:
    def __init__(self, path: str = "server_data.db"):
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._create_schema()

    def _create_schema(self):
        with self._lock, self._conn:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    public_key TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS offline_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    payload TEXT NOT NULL
                )
            """)

    # ---- usuários (seção 7.1) ----

    def username_exists(self, username: str) -> bool:
        with self._lock:
            cur = self._conn.execute("SELECT 1 FROM users WHERE username = ?", (username,))
            return cur.fetchone() is not None

    def create_user(self, username: str, password_hash: str, public_key_b64: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO users (username, password_hash, public_key, created_at) VALUES (?, ?, ?, ?)",
                (username, password_hash, public_key_b64, time.time()),
            )

    def get_user(self, username: str):
        with self._lock:
            cur = self._conn.execute(
                "SELECT username, password_hash, public_key FROM users WHERE username = ?", (username,)
            )
            row = cur.fetchone()
            if row is None:
                return None
            return {"username": row[0], "password_hash": row[1], "public_key": row[2]}

    def update_public_key(self, username: str, public_key_b64: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("UPDATE users SET public_key = ? WHERE username = ?", (public_key_b64, username))

    def all_usernames(self):
        with self._lock:
            cur = self._conn.execute("SELECT username FROM users")
            return [row[0] for row in cur.fetchall()]

    # ---- fila offline (seções 5.8 e 8.4) ----

    def queue_offline_message(self, sender: str, recipient: str, timestamp: float, payload: dict) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO offline_messages (sender, recipient, timestamp, payload) VALUES (?, ?, ?, ?)",
                (sender, recipient, timestamp, json.dumps(payload)),
            )

    def pop_offline_messages(self, recipient: str):
        with self._lock, self._conn:
            cur = self._conn.execute(
                "SELECT id, sender, timestamp, payload FROM offline_messages WHERE recipient = ? ORDER BY id",
                (recipient,),
            )
            rows = cur.fetchall()
            ids = [row[0] for row in rows]
            if ids:
                placeholders = ",".join("?" for _ in ids)
                self._conn.execute(f"DELETE FROM offline_messages WHERE id IN ({placeholders})", ids)
            return [
                {"sender": row[1], "timestamp": row[2], "payload": json.loads(row[3])}
                for row in rows
            ]

    def discard_offline_messages(self, username: str) -> None:
        """Usado quando o usuário troca de dispositivo (seção 7.3)."""
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM offline_messages WHERE recipient = ?", (username,))
