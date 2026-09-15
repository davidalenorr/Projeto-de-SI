"""Sessão do canal seguro entre o servidor e um cliente conectado.

Guarda só o que é efêmero: as chaves derivadas e o contador de mensagens. Quem
decide QUANDO renovar é sempre o cliente (é ele quem "requisita uma nova
comunicação", seção 6.1); o servidor apenas responde ao handshake ou à
renovação que chegar.
"""
import json
import time

from security import primitives


class ChannelSession:
    def __init__(self):
        self.key_aes = None
        self.key_hmac = None
        self.established_at = None
        self.message_count = 0

    @property
    def is_established(self) -> bool:
        return self.key_aes is not None

    def complete_handshake(self, dh_private, peer_public_bytes: bytes, salt: bytes) -> None:
        shared_secret = primitives.dh_shared_secret(dh_private, peer_public_bytes)
        self.key_aes, self.key_hmac = primitives.derive_session_keys(shared_secret, salt)
        self.established_at = time.time()
        self.message_count = 0

    def seal(self, payload: dict) -> dict:
        plaintext = json.dumps(payload).encode("utf-8")
        self.message_count += 1
        return primitives.seal(self.key_aes, self.key_hmac, plaintext)

    def open(self, envelope: dict) -> dict:
        plaintext = primitives.open_sealed(self.key_aes, self.key_hmac, envelope)
        return json.loads(plaintext.decode("utf-8"))
