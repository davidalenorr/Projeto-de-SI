"""Regras de registro e autenticação (seção 7 do Projeto 2).

Esta camada não sabe nada de socket: recebe dados já decifrados pelo canal
seguro e devolve decisões. Quem fala com a rede é o ClientHandler.
"""
import os

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from security import primitives


class AuthService:
    def __init__(self, db):
        self._db = db
        # PasswordHasher já gera e embute um salt aleatório por chamada de
        # hash(), o que atende ao requisito de "todo usuário tem um salt
        # diferente" sem precisar de uma coluna extra no banco.
        self._hasher = PasswordHasher()

    def register(self, username: str, password: str, public_key_b64: str):
        if self._db.username_exists(username):
            return False, "nome de usuário já está em uso"
        password_hash = self._hasher.hash(password)
        self._db.create_user(username, password_hash, public_key_b64)
        return True, None

    def verify_password(self, username: str, password: str) -> bool:
        user = self._db.get_user(username)
        if user is None:
            return False
        try:
            self._hasher.verify(user["password_hash"], password)
            return True
        except VerifyMismatchError:
            return False

    def get_public_key(self, username: str):
        user = self._db.get_user(username)
        return user["public_key"] if user else None

    def new_nonce(self) -> bytes:
        return os.urandom(32)

    def verify_device_signature(self, username: str, nonce: bytes, signature_b64: str) -> bool:
        """Autenticação em dispositivo já conhecido, sem senha (seção 7.2)."""
        public_key_b64 = self.get_public_key(username)
        if public_key_b64 is None:
            return False
        public_key_bytes = primitives.b64d(public_key_b64)
        signature = primitives.b64d(signature_b64)
        return primitives.verify_signature(public_key_bytes, nonce, signature)

    def replace_device(self, username: str, password: str, new_public_key_b64: str) -> bool:
        """Autenticação a partir de um novo dispositivo (seção 7.3)."""
        if not self.verify_password(username, password):
            return False
        self._db.update_public_key(username, new_public_key_b64)
        self._db.discard_offline_messages(username)
        return True
