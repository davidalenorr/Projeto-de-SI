"""Sessões E2EE com cada contato (Projeto 2, seção 8). O servidor nunca vê
estas chaves — elas usam um `info` diferente do HKDF do canal (seção 8.1:
"essas chaves ... devem ser diferentes das usadas entre cada usuário e o
servidor"), e uma política de expiração análoga à do canal.
"""
import json
import random
import time

from security import primitives
from security.channel_session import (
    MAX_SESSION_MESSAGES, MAX_SESSION_SECONDS, MIN_SESSION_MESSAGES, MIN_SESSION_SECONDS,
)


class PeerSession:
    def __init__(self, contact: str):
        self.contact = contact
        self.key_aes = None
        self.key_hmac = None
        self.established_at = None
        self.message_count = 0
        self.authenticated = False
        self._max_seconds = None
        self._max_messages = None
        self._pending_private = None
        self._pending_salt = None

    @property
    def is_established(self) -> bool:
        return self.key_aes is not None

    def needs_renewal(self) -> bool:
        if not self.is_established:
            return True
        elapsed = time.time() - self.established_at
        return elapsed >= self._max_seconds or self.message_count >= self._max_messages

    def start_handshake(self):
        """Chamado por quem inicia o handshake (seção 8.1: "pode ser tanto A quanto B")."""
        dh_private, dh_public = primitives.generate_dh_keypair()
        salt = primitives.generate_salt()
        self._pending_private = dh_private
        self._pending_salt = salt
        return dh_public, salt

    def respond_handshake(self, peer_public_bytes: bytes, salt: bytes):
        """Chamado por quem recebe o pedido: também precisa de um par efêmero."""
        dh_private, dh_public = primitives.generate_dh_keypair()
        self._finish(dh_private, peer_public_bytes, salt)
        return dh_public

    def complete_as_initiator(self, peer_public_bytes: bytes):
        self._finish(self._pending_private, peer_public_bytes, self._pending_salt)

    def _finish(self, private_key, peer_public_bytes: bytes, salt: bytes):
        shared_secret = primitives.dh_shared_secret(private_key, peer_public_bytes)
        self.key_aes, self.key_hmac = primitives.derive_session_keys(
            shared_secret, salt, info=b"chat-e2ee-peer"
        )
        self.established_at = time.time()
        self.message_count = 0
        self.authenticated = False
        self._max_seconds = random.uniform(MIN_SESSION_SECONDS, MAX_SESSION_SECONDS)
        self._max_messages = random.randint(MIN_SESSION_MESSAGES, MAX_SESSION_MESSAGES)

    def seal(self, payload: dict) -> dict:
        plaintext = json.dumps(payload).encode("utf-8")
        self.message_count += 1
        return primitives.seal(self.key_aes, self.key_hmac, plaintext)

    def open(self, envelope: dict) -> dict:
        plaintext = primitives.open_sealed(self.key_aes, self.key_hmac, envelope)
        return json.loads(plaintext.decode("utf-8"))
