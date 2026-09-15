"""Histórico local de conversas, cifrado com AES-256 (seção 8.5 do Projeto 2)
e o requisito de histórico do Projeto 1 (seção 5.9).

A "chave que só o próprio usuário conhece" é a chave mestra local
(security.keystore.load_or_create_local_master_key). Duas subchaves (uma para
AES, outra para HMAC) são derivadas dela por HKDF, para não reaproveitar a
mesma chave em dois algoritmos diferentes.
"""
import sqlite3
import threading

from security import primitives


class LocalDatabase:
    def __init__(self, path: str, local_master_key: bytes):
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._key_aes, self._key_hmac = primitives.derive_session_keys(
            local_master_key, salt=b"chat-client-local-history", info=b"local-history"
        )
        self._create_schema()

    def _create_schema(self):
        with self._lock, self._conn:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contact TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    iv TEXT NOT NULL,
                    ciphertext TEXT NOT NULL,
                    mac TEXT NOT NULL
                )
            """)

    def save_message(self, contact: str, direction: str, timestamp: float, text: str) -> None:
        envelope = primitives.seal(self._key_aes, self._key_hmac, text.encode("utf-8"))
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO messages (contact, direction, timestamp, iv, ciphertext, mac) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (contact, direction, timestamp, envelope["iv"], envelope["ciphertext"], envelope["mac"]),
            )

    def history_with(self, contact: str):
        with self._lock:
            cur = self._conn.execute(
                "SELECT direction, timestamp, iv, ciphertext, mac FROM messages "
                "WHERE contact = ? ORDER BY timestamp",
                (contact,),
            )
            rows = cur.fetchall()
        history = []
        for direction, timestamp, iv, ciphertext, mac in rows:
            text = primitives.open_sealed(
                self._key_aes, self._key_hmac, {"iv": iv, "ciphertext": ciphertext, "mac": mac}
            ).decode("utf-8")
            history.append({"direction": direction, "timestamp": timestamp, "text": text})
        return history
