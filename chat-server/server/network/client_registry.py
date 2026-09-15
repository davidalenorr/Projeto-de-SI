"""Registro dos clientes conectados agora — é aqui, e só aqui, que se sabe
quem está online (seção 5.7). Threads diferentes (uma por cliente) leem e
escrevem este registro, por isso todo acesso passa pelo lock.
"""
import threading


class ClientRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._handlers = {}  # username -> ClientHandler

    def add(self, username: str, handler) -> None:
        with self._lock:
            self._handlers[username] = handler

    def remove(self, username: str) -> None:
        with self._lock:
            self._handlers.pop(username, None)

    def get(self, username: str):
        with self._lock:
            return self._handlers.get(username)

    def online_usernames(self):
        with self._lock:
            return set(self._handlers.keys())
