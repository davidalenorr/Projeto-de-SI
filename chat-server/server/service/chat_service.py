"""Regras do chat em si: contatos, presença, roteamento e fila offline
(seções 5.3 a 5.9 do Projeto 1, e 8.4 do Projeto 2).

Esta camada decide O QUE fazer; quem entrega de fato no socket certo é o
ClientHandler de cada conexão, através do ClientRegistry.
"""
import time

import protocol


class ChatService:
    def __init__(self, db, registry):
        self._db = db
        self._registry = registry

    def contacts_snapshot(self):
        online = self._registry.online_usernames()
        return [{"username": u, "online": u in online} for u in self._db.all_usernames()]

    def broadcast_presence(self, username: str, online: bool):
        for other in self._registry.online_usernames():
            if other == username:
                continue
            handler = self._registry.get(other)
            if handler:
                handler.send_event(protocol.PRESENCE_UPDATE, {"username": username, "online": online})

    def send_contacts_list(self, handler):
        handler.send_event(protocol.CONTACTS_LIST, {"contacts": self.contacts_snapshot()})

    def deliver_offline_queue(self, username: str, handler):
        messages = self._db.pop_offline_messages(username)
        if messages:
            handler.send_event(protocol.OFFLINE_QUEUE, {"messages": messages})

    def route_peer_frame(self, sender: str, payload: dict):
        recipient = payload.get("to")
        target = self._registry.get(recipient)
        if target:
            target.send_event(protocol.PEER_FRAME, payload)
        else:
            self._db.queue_offline_message(sender, recipient, time.time(), payload)

    def route_handshake(self, event_type: str, payload: dict, source_handler):
        recipient = payload.get("to")
        target = self._registry.get(recipient)
        if target is None:
            source_handler.send_event(protocol.ERROR, {
                "message": f"{recipient} está offline: não é possível negociar o handshake agora",
            })
            return
        target.send_event(event_type, payload)

    def route_typing(self, sender: str, payload: dict, active: bool):
        recipient = payload.get("to")
        target = self._registry.get(recipient)
        if target:
            target.send_event(protocol.TYPING_NOTICE, {"from": sender, "active": active})

    def handle_pubkey_request(self, requester: str, target_username: str,
                               requester_public_key_b64: str, auth_service, handler):
        target_public_key = auth_service.get_public_key(target_username)
        if target_public_key is None:
            handler.send_event(protocol.ERROR, {"message": f"usuário {target_username} não existe"})
            return
        handler.send_event(protocol.PUBKEY_RESPONSE, {
            "username": target_username, "public_key": target_public_key,
        })
        target_handler = self._registry.get(target_username)
        if target_handler and requester_public_key_b64:
            target_handler.send_event(protocol.PEER_INCOMING_KEY, {
                "username": requester, "public_key": requester_public_key_b64,
            })

    def notify_key_changed(self, username: str):
        for other in self._registry.online_usernames():
            handler = self._registry.get(other)
            if handler:
                handler.send_event(protocol.KEY_CHANGED_NOTICE, {"username": username})
