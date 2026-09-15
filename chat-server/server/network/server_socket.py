"""Camada de rede do servidor: uma thread de escuta e uma thread por cliente
(seção 6.5 do Projeto 1, Figura 7).

Esta camada não decide regra de negócio nenhuma; ela só fala socket e delega
para AuthService/ChatService o que fazer com cada evento já decifrado.
"""
import socket
import threading

import protocol
from security import primitives
from security.channel_session import ChannelSession


class ClientHandler(threading.Thread):
    def __init__(self, sock, address, auth_service, chat_service, registry):
        super().__init__(daemon=True)
        self._sock = sock
        self._address = address
        self._auth = auth_service
        self._chat = chat_service
        self._registry = registry
        self._session = ChannelSession()
        self._send_lock = threading.Lock()
        self._username = None
        self._pending_login_username = None
        self._pending_nonce = None

    # ---- envio (chamado por outras threads também, por isso o lock) ----

    def send_event(self, event_type: str, payload: dict) -> None:
        payload = dict(payload)
        payload["type"] = event_type
        with self._send_lock:
            if self._session.is_established:
                envelope = self._session.seal(payload)
                envelope["type"] = protocol.SECURE
                protocol.send_frame(self._sock, envelope)
            else:
                protocol.send_frame(self._sock, payload)

    def _send_raw(self, payload: dict) -> None:
        with self._send_lock:
            protocol.send_frame(self._sock, payload)

    # ---- ciclo de vida da conexão ----

    def run(self):
        try:
            self._await_channel_handshake()
            while True:
                frame = protocol.recv_frame(self._sock)
                if frame.get("type") != protocol.SECURE:
                    continue  # após o handshake inicial só se aceita tráfego cifrado
                event = self._session.open(frame)
                self._dispatch(event)
        except (protocol.ConnectionClosed, OSError):
            pass
        finally:
            self._on_disconnect()

    def _await_channel_handshake(self):
        frame = protocol.recv_frame(self._sock)
        if frame.get("type") != protocol.CHANNEL_HELLO:
            raise protocol.ConnectionClosed("handshake inválido")
        client_public = primitives.b64d(frame["dh_public"])
        salt = primitives.b64d(frame["salt"])
        server_private, server_public = primitives.generate_dh_keypair()
        self._session.complete_handshake(server_private, client_public, salt)
        self._send_raw({"type": protocol.CHANNEL_HELLO_ACK, "dh_public": primitives.b64e(server_public)})

    def _dispatch(self, event: dict):
        handlers = {
            protocol.CHANNEL_REKEY: self._on_channel_rekey,
            protocol.REGISTER: self._on_register,
            protocol.LOGIN_DEVICE: self._on_login_device,
            protocol.LOGIN_CHALLENGE_RESPONSE: self._on_login_challenge_response,
            protocol.LOGIN_NEW_DEVICE: self._on_login_new_device,
            protocol.PUBKEY_REQUEST: self._on_pubkey_request,
            protocol.PEER_HANDSHAKE_INIT: self._on_peer_route,
            protocol.PEER_HANDSHAKE_ACK: self._on_peer_route,
            protocol.PEER_FRAME: self._on_peer_frame,
            protocol.TYPING_START: lambda e: self._on_typing(e, True),
            protocol.TYPING_STOP: lambda e: self._on_typing(e, False),
        }
        handler = handlers.get(event.get("type"))
        if handler:
            handler(event)

    # ---- renovação do canal (seção 6.4) ----

    def _on_channel_rekey(self, event):
        # Mesma peça do handshake inicial, mas viajando dentro do envelope
        # seguro anterior: é isso que esconde o momento da renovação.
        client_public = primitives.b64d(event["dh_public"])
        salt = primitives.b64d(event["salt"])
        server_private, server_public = primitives.generate_dh_keypair()
        self.send_event(protocol.CHANNEL_REKEY_ACK, {"dh_public": primitives.b64e(server_public)})
        self._session.complete_handshake(server_private, client_public, salt)

    # ---- autenticação (seção 7) ----

    def _on_register(self, event):
        success, reason = self._auth.register(event["username"], event["password"], event["public_key"])
        self.send_event(protocol.REGISTER_RESPONSE, {"success": success, "reason": reason})

    def _on_login_device(self, event):
        username = event["username"]
        if self._auth.get_public_key(username) is None:
            self.send_event(protocol.LOGIN_RESPONSE, {"success": False, "reason": "usuário não existe"})
            return
        self._pending_login_username = username
        self._pending_nonce = self._auth.new_nonce()
        self.send_event(protocol.LOGIN_CHALLENGE, {"nonce": primitives.b64e(self._pending_nonce)})

    def _on_login_challenge_response(self, event):
        username = self._pending_login_username
        nonce = self._pending_nonce
        self._pending_login_username = None
        self._pending_nonce = None
        if username is None or nonce is None:
            return
        if self._auth.verify_device_signature(username, nonce, event["signature"]):
            self._finish_login(username)
        else:
            self.send_event(protocol.LOGIN_RESPONSE, {"success": False, "reason": "assinatura inválida"})

    def _on_login_new_device(self, event):
        username = event["username"]
        if self._auth.replace_device(username, event["password"], event["public_key"]):
            self._chat.notify_key_changed(username)
            self._finish_login(username)
        else:
            self.send_event(protocol.LOGIN_RESPONSE, {"success": False, "reason": "usuário ou senha inválidos"})

    def _finish_login(self, username: str):
        self._username = username
        self._registry.add(username, self)
        self.send_event(protocol.LOGIN_RESPONSE, {"success": True, "reason": None})
        self._chat.send_contacts_list(self)
        self._chat.broadcast_presence(username, True)
        self._chat.deliver_offline_queue(username, self)

    # ---- chat (seções 5.4 a 5.6, 8.1, 8.4) ----

    def _on_pubkey_request(self, event):
        if not self._username:
            return
        self._chat.handle_pubkey_request(
            self._username, event["of_username"],
            self._auth.get_public_key(self._username), self._auth, self,
        )

    def _on_peer_route(self, event):
        if not self._username:
            return
        self._chat.route_handshake(event["type"], event, self)

    def _on_peer_frame(self, event):
        if not self._username:
            return
        self._chat.route_peer_frame(self._username, event)

    def _on_typing(self, event, active: bool):
        if not self._username:
            return
        self._chat.route_typing(self._username, event, active)

    def _on_disconnect(self):
        if self._username:
            self._registry.remove(self._username)
            self._chat.broadcast_presence(self._username, False)
        try:
            self._sock.close()
        except OSError:
            pass


class ChatServer:
    def __init__(self, host, port, auth_service, chat_service, registry):
        self._host = host
        self._port = port
        self._auth = auth_service
        self._chat = chat_service
        self._registry = registry

    def serve_forever(self):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((self._host, self._port))
        listener.listen()
        print(f"Servidor escutando em {self._host}:{self._port}")
        while True:
            client_sock, address = listener.accept()
            handler = ClientHandler(client_sock, address, self._auth, self._chat, self._registry)
            handler.start()
