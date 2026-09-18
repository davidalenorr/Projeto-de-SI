"""Orquestra registro e login, e guarda a identidade do usuário logado
(Projeto 2, seção 7).

Decide sozinho qual dos dois logins usar: se este dispositivo já tem uma
identidade local para o nome de usuário informado, usa login_known_device,
que confere a senha no servidor e também prova a posse do dispositivo por
desafio assinado (7.2); caso contrário, quem chama deve usar
login_new_device, que registra este dispositivo como o novo autenticado
(7.3). Em ambos os casos a senha é exigida na tela de login.
"""
import protocol
from security import keystore, primitives


class SessionService:
    def __init__(self, connection, app_events):
        self._connection = connection
        self._events = app_events
        self.username = None
        self.identity_public_key = None
        self.local_master_key = None
        self._identity_private_key = None

        self._events.on(protocol.LOGIN_CHALLENGE, self._on_login_challenge)

    def is_known_device(self, username: str) -> bool:
        return keystore.has_identity(username)

    def register(self, username: str, password: str) -> None:
        private_key, public_key_bytes = keystore.create_identity(username)
        self._identity_private_key = private_key
        self.identity_public_key = public_key_bytes
        self._connection.send_event(protocol.REGISTER, {
            "username": username,
            "password": password,
            "public_key": primitives.b64e(public_key_bytes),
        })

    def login_known_device(self, username: str, password: str) -> None:
        self._identity_private_key, self.identity_public_key = keystore.load_identity(username)
        self.username = username
        self._connection.send_event(protocol.LOGIN_DEVICE, {"username": username, "password": password})

    def login_new_device(self, username: str, password: str) -> None:
        private_key, public_key_bytes = keystore.create_identity(username)
        self._identity_private_key = private_key
        self.identity_public_key = public_key_bytes
        self.username = username
        self._connection.send_event(protocol.LOGIN_NEW_DEVICE, {
            "username": username,
            "password": password,
            "public_key": primitives.b64e(public_key_bytes),
        })

    def sign_with_identity(self, data: bytes) -> bytes:
        return primitives.sign(self._identity_private_key, data)

    def finish_login(self) -> None:
        """Chamado pela GUI após um login_response de sucesso."""
        self.local_master_key = keystore.load_or_create_local_master_key(self.username)

    def _on_login_challenge(self, event):
        nonce = primitives.b64d(event["nonce"])
        signature = self.sign_with_identity(nonce)
        self._connection.send_event(protocol.LOGIN_CHALLENGE_RESPONSE, {
            "signature": primitives.b64e(signature),
        })
