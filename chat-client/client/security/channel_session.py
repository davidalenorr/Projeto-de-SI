"""Sessão do canal seguro entre este cliente e o servidor.

Ao contrário do servidor, é aqui que mora a decisão de QUANDO renovar
(seção 6.4): a duração da sessão e o número de mensagens trocadas, com a
variação aleatória sugerida como melhoria — isso esconde o padrão de
expiração ("o que derrubou o Enigma foi um padrão previsível").
"""
import json
import random
import time

from security import primitives

MIN_SESSION_SECONDS = 30 * 60
MAX_SESSION_SECONDS = 60 * 60
MIN_SESSION_MESSAGES = 50
MAX_SESSION_MESSAGES = 100


class ChannelSession:
    def __init__(self):
        self.key_aes = None
        self.key_hmac = None
        self.established_at = None
        self.message_count = 0
        self._max_seconds = None
        self._max_messages = None
        self._pending_private = None
        self._pending_salt = None

    @property
    def is_established(self) -> bool:
        return self.key_aes is not None

    def needs_renewal(self) -> bool:
        if not self.is_established:
            return False
        elapsed = time.time() - self.established_at
        return elapsed >= self._max_seconds or self.message_count >= self._max_messages

    def start_handshake(self):
        dh_private, dh_public = primitives.generate_dh_keypair()
        salt = primitives.generate_salt()
        self._pending_private = dh_private
        self._pending_salt = salt
        return dh_public, salt

    def complete_handshake(self, server_public_bytes: bytes):
        shared_secret = primitives.dh_shared_secret(self._pending_private, server_public_bytes)
        self.key_aes, self.key_hmac = primitives.derive_session_keys(shared_secret, self._pending_salt)
        self.established_at = time.time()
        self.message_count = 0
        self._max_seconds = random.uniform(MIN_SESSION_SECONDS, MAX_SESSION_SECONDS)
        self._max_messages = random.randint(MIN_SESSION_MESSAGES, MAX_SESSION_MESSAGES)

    def seal(self, payload: dict) -> dict:
        plaintext = json.dumps(payload).encode("utf-8")
        self.message_count += 1
        return primitives.seal(self.key_aes, self.key_hmac, plaintext)

    def open(self, envelope: dict) -> dict:
        plaintext = primitives.open_sealed(self.key_aes, self.key_hmac, envelope)
        return json.loads(plaintext.decode("utf-8"))
