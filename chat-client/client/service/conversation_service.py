"""Conversa ponta a ponta com um contato: distribuição de chave pública,
handshake E2E, autenticação mútua, envio/recebimento de mensagens e o
indicador de digitação (Projeto 1, seções 5.4-5.6; Projeto 2, seção 8).

Cada mensagem de aplicação (`peer_frame`) carrega um envelope E2E já cifrado
com as chaves do par (A, B) — o `inner`. Esse `peer_frame` inteiro é então
enviado como um evento comum pela Connection, que o embrulha de novo com as
chaves do canal com o servidor. É assim que as duas camadas da Figura 9 do
Projeto 2 se formam, sem precisar de nenhuma lógica extra aqui.
"""
import time

import protocol
from security import primitives
from security.e2e_session import PeerSession


class ConversationService:
    def __init__(self, connection, app_events, session_service, contacts_service, local_db):
        self._connection = connection
        self._events = app_events
        self._session_service = session_service
        self._contacts_service = contacts_service
        self._local_db = local_db

        self._peers = {}             # contact -> PeerSession
        self._peer_public_keys = {}  # contact -> bytes
        self._nonces_sent = {}       # contact -> nonce aguardando verificação

        self.message_listeners = []  # callback(contact, direction, text, timestamp)
        self.typing_listeners = []   # callback(contact, active)
        self.error_listeners = []    # callback(message)

        self._events.on(protocol.PUBKEY_RESPONSE, self._on_pubkey_response)
        self._events.on(protocol.PEER_INCOMING_KEY, self._on_peer_incoming_key)
        self._events.on(protocol.PEER_HANDSHAKE_INIT, self._on_peer_handshake_init)
        self._events.on(protocol.PEER_HANDSHAKE_ACK, self._on_peer_handshake_ack)
        self._events.on(protocol.PEER_FRAME, self._on_peer_frame)
        self._events.on(protocol.TYPING_NOTICE, self._on_typing_notice)
        self._events.on(protocol.OFFLINE_QUEUE, self._on_offline_queue)
        self._events.on(protocol.KEY_CHANGED_NOTICE, self._on_key_changed)
        self._events.on(protocol.ERROR, self._on_error)

    # ---- API usada pela GUI ----

    def history_with(self, contact: str):
        return self._local_db.history_with(contact)

    def has_ready_session_with(self, contact: str) -> bool:
        peer = self._peers.get(contact)
        return bool(peer and peer.is_established and peer.authenticated and not peer.needs_renewal())

    def ensure_session(self, contact: str) -> None:
        """Garante (de forma assíncrona) uma sessão E2E válida com o contato."""
        if self.has_ready_session_with(contact):
            return
        self._connection.send_event(protocol.PUBKEY_REQUEST, {"of_username": contact})

    def send_message(self, contact: str, text: str) -> None:
        if not self.has_ready_session_with(contact):
            if not self._contacts_service.is_online(contact):
                self._notify_error(
                    f"{contact} está offline e nunca houve uma sessão segura com ele: "
                    f"a mensagem não pode ser entregue por questão de segurança"
                )
            else:
                self._notify_error(f"estabelecendo uma sessão segura com {contact}; tente enviar de novo em instantes")
                self.ensure_session(contact)
            return
        peer = self._peers[contact]
        timestamp = time.time()
        inner = peer.seal({"kind": "chat_message", "text": text})
        self._connection.send_event(protocol.PEER_FRAME, {
            "subtype": "chat_message",
            "to": contact,
            "from": self._session_service.username,
            "timestamp": timestamp,
            "inner": inner,
        })
        self._local_db.save_message(contact, "sent", timestamp, text)
        self._notify_message(contact, "sent", text, timestamp)

    def send_typing(self, contact: str, active: bool) -> None:
        event_type = protocol.TYPING_START if active else protocol.TYPING_STOP
        self._connection.send_event(event_type, {"to": contact})

    # ---- distribuição de chave pública (seção 7.4) ----

    def _on_pubkey_response(self, event):
        contact = event["username"]
        self._peer_public_keys[contact] = primitives.b64d(event["public_key"])
        self._start_handshake(contact)

    def _on_peer_incoming_key(self, event):
        self._peer_public_keys[event["username"]] = primitives.b64d(event["public_key"])

    # ---- handshake E2E (seção 8.1) ----

    def _start_handshake(self, contact: str):
        peer = PeerSession(contact)
        self._peers[contact] = peer
        dh_public, salt = peer.start_handshake()
        self._connection.send_event(protocol.PEER_HANDSHAKE_INIT, {
            "to": contact,
            "from": self._session_service.username,
            "dh_public": primitives.b64e(dh_public),
            "salt": primitives.b64e(salt),
        })

    def _on_peer_handshake_init(self, event):
        contact = event["from"]
        peer = PeerSession(contact)
        self._peers[contact] = peer
        dh_public = peer.respond_handshake(
            primitives.b64d(event["dh_public"]), primitives.b64d(event["salt"])
        )
        self._connection.send_event(protocol.PEER_HANDSHAKE_ACK, {
            "to": contact,
            "from": self._session_service.username,
            "dh_public": primitives.b64e(dh_public),
        })
        self._begin_mutual_auth(contact)

    def _on_peer_handshake_ack(self, event):
        contact = event["from"]
        peer = self._peers.get(contact)
        if peer is None:
            return
        peer.complete_as_initiator(primitives.b64d(event["dh_public"]))
        self._begin_mutual_auth(contact)

    # ---- autenticação mútua (seção 8.3) ----

    def _begin_mutual_auth(self, contact: str):
        peer = self._peers[contact]
        nonce = primitives.generate_salt(16)
        self._nonces_sent[contact] = nonce
        inner = peer.seal({"kind": "auth_challenge", "nonce": primitives.b64e(nonce)})
        self._connection.send_event(protocol.PEER_FRAME, {
            "subtype": "auth", "to": contact, "from": self._session_service.username, "inner": inner,
        })

    def _handle_auth_frame(self, contact: str, inner: dict):
        peer = self._peers[contact]
        if inner.get("kind") == "auth_challenge":
            nonce = primitives.b64d(inner["nonce"])
            signature = self._session_service.sign_with_identity(nonce)
            response = peer.seal({"kind": "auth_response", "signature": primitives.b64e(signature)})
            self._connection.send_event(protocol.PEER_FRAME, {
                "subtype": "auth", "to": contact, "from": self._session_service.username, "inner": response,
            })
        elif inner.get("kind") == "auth_response":
            nonce = self._nonces_sent.pop(contact, None)
            public_key = self._peer_public_keys.get(contact)
            signature = primitives.b64d(inner["signature"])
            if nonce and public_key and primitives.verify_signature(public_key, nonce, signature):
                peer.authenticated = True
            else:
                self._notify_error(f"autenticação de {contact} falhou; sessão descartada")
                self._peers.pop(contact, None)

    # ---- mensagens e roteamento genérico de peer_frame ----

    def _on_peer_frame(self, event):
        contact = event["from"]
        peer = self._peers.get(contact)
        if peer is None:
            return
        try:
            inner = peer.open(event["inner"])
        except primitives.IntegrityError:
            self._notify_error(f"mensagem de {contact} descartada: integridade inválida")
            return
        subtype = event.get("subtype")
        if subtype == "auth":
            self._handle_auth_frame(contact, inner)
        elif subtype == "chat_message":
            timestamp = event["timestamp"]
            self._local_db.save_message(contact, "received", timestamp, inner["text"])
            self._notify_message(contact, "received", inner["text"], timestamp)

    # ---- fila offline (seção 8.4) ----

    def _on_offline_queue(self, event):
        for item in event["messages"]:
            contact = item["sender"]
            payload = item["payload"]
            peer = self._peers.get(contact)
            if peer is None or not peer.is_established:
                self._notify_error(f"mensagem de {contact} recebida offline não pôde ser aberta: sem sessão E2E")
                continue
            try:
                inner = peer.open(payload["inner"])
            except primitives.IntegrityError:
                continue
            self._local_db.save_message(contact, "received", item["timestamp"], inner["text"])
            self._notify_message(contact, "received", inner["text"], item["timestamp"])

    def _on_typing_notice(self, event):
        for cb in self.typing_listeners:
            cb(event["from"], event["active"])

    def _on_key_changed(self, event):
        # A chave pública do contato mudou (troca de dispositivo, seção 7.3):
        # a sessão antiga não vale mais nada.
        self._peers.pop(event["username"], None)
        self._peer_public_keys.pop(event["username"], None)

    def _on_error(self, event):
        self._notify_error(event["message"])

    def _notify_message(self, contact, direction, text, timestamp):
        for cb in self.message_listeners:
            cb(contact, direction, text, timestamp)

    def _notify_error(self, message):
        for cb in self.error_listeners:
            cb(message)
