"""Conexão com o servidor: socket + thread de recepção + thread de envio.

Três threads mínimas trabalham aqui, seguindo a Figura 7 do Projeto 1: a
thread da interface (Tkinter, em outro módulo) nunca toca o socket
diretamente — ela só empilha eventos para enviar e lê uma fila de eventos
recebidos. Isso evita o erro mais comum do projeto: a tela travar porque quem
a desenha é quem está parado esperando o socket.
"""
import queue
import socket
import threading

import protocol
from security import primitives
from security.channel_session import ChannelSession


class Connection:
    def __init__(self, host: str, port: int):
        self._host = host
        self._port = port
        self._sock = None
        self._session = ChannelSession()
        self._send_lock = threading.Lock()
        self._outbox = queue.Queue()
        self.inbox = queue.Queue()  # eventos de aplicação já decifrados, para a GUI consumir
        self._rekey_event = threading.Event()

    def start(self) -> None:
        self._sock = socket.create_connection((self._host, self._port))
        self._do_channel_handshake()
        threading.Thread(target=self._receive_loop, daemon=True).start()
        threading.Thread(target=self._send_loop, daemon=True).start()

    def _do_channel_handshake(self) -> None:
        dh_public, salt = self._session.start_handshake()
        protocol.send_frame(self._sock, {
            "type": protocol.CHANNEL_HELLO,
            "dh_public": primitives.b64e(dh_public),
            "salt": primitives.b64e(salt),
        })
        ack = protocol.recv_frame(self._sock)
        server_public = primitives.b64d(ack["dh_public"])
        self._session.complete_handshake(server_public)

    def _receive_loop(self) -> None:
        try:
            while True:
                frame = protocol.recv_frame(self._sock)
                if frame.get("type") != protocol.SECURE:
                    continue
                event = self._session.open(frame)
                if event.get("type") == protocol.CHANNEL_REKEY_ACK:
                    self._session.complete_handshake(primitives.b64d(event["dh_public"]))
                    self._rekey_event.set()
                    continue
                self.inbox.put(event)
        except (protocol.ConnectionClosed, OSError):
            self.inbox.put({"type": "connection_lost"})

    def _send_loop(self) -> None:
        while True:
            event_type, payload = self._outbox.get()
            try:
                self._renew_if_needed()
                payload = dict(payload)
                payload["type"] = event_type
                envelope = self._session.seal(payload)
                envelope["type"] = protocol.SECURE
                with self._send_lock:
                    protocol.send_frame(self._sock, envelope)
            except (protocol.ConnectionClosed, OSError):
                self.inbox.put({"type": "connection_lost"})
                return

    def _renew_if_needed(self) -> None:
        if not self._session.needs_renewal():
            return
        dh_public, salt = self._session.start_handshake()
        self._rekey_event.clear()
        rekey_payload = {
            "type": protocol.CHANNEL_REKEY,
            "dh_public": primitives.b64e(dh_public),
            "salt": primitives.b64e(salt),
        }
        envelope = self._session.seal(rekey_payload)
        envelope["type"] = protocol.SECURE
        with self._send_lock:
            protocol.send_frame(self._sock, envelope)
        self._rekey_event.wait(timeout=10)

    def send_event(self, event_type: str, payload: dict) -> None:
        """Não bloqueia: só empilha. Quem envia de fato é a thread de envio."""
        self._outbox.put((event_type, payload))

    def close(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass
