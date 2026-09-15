"""Formato do pacote trocado entre cliente e servidor.

Este arquivo é intencionalmente idêntico ao `protocol.py` do repositório do
servidor: os dois lados precisam concordar byte a byte sobre o framing e o
nome de cada evento, e os documentos do projeto tratam cliente e servidor
como repositórios Git separados (sem pacote compartilhado entre eles).
"""
import json
import struct

_LENGTH_PREFIX = ">I"
_LENGTH_PREFIX_SIZE = 4


class ConnectionClosed(Exception):
    pass


def send_frame(sock, payload: dict) -> None:
    data = json.dumps(payload).encode("utf-8")
    sock.sendall(struct.pack(_LENGTH_PREFIX, len(data)) + data)


def _recv_exact(sock, n: int) -> bytes:
    chunks = []
    remaining = n
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise ConnectionClosed("conexão encerrada pelo outro lado")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def recv_frame(sock) -> dict:
    header = _recv_exact(sock, _LENGTH_PREFIX_SIZE)
    (length,) = struct.unpack(_LENGTH_PREFIX, header)
    data = _recv_exact(sock, length)
    return json.loads(data.decode("utf-8"))


# ---- Tipos de evento do protocolo ----

CHANNEL_HELLO = "channel_hello"
CHANNEL_HELLO_ACK = "channel_hello_ack"
CHANNEL_REKEY = "channel_rekey"
CHANNEL_REKEY_ACK = "channel_rekey_ack"
SECURE = "secure"

REGISTER = "register"
REGISTER_RESPONSE = "register_response"

LOGIN_DEVICE = "login_device"
LOGIN_NEW_DEVICE = "login_new_device"
LOGIN_CHALLENGE = "login_challenge"
LOGIN_CHALLENGE_RESPONSE = "login_challenge_response"
LOGIN_RESPONSE = "login_response"

CONTACTS_LIST = "contacts_list"
PRESENCE_UPDATE = "presence_update"

PUBKEY_REQUEST = "pubkey_request"
PUBKEY_RESPONSE = "pubkey_response"
PEER_INCOMING_KEY = "peer_incoming_key"
KEY_CHANGED_NOTICE = "key_changed_notice"

PEER_HANDSHAKE_INIT = "peer_handshake_init"
PEER_HANDSHAKE_ACK = "peer_handshake_ack"
PEER_FRAME = "peer_frame"

TYPING_START = "typing_start"
TYPING_STOP = "typing_stop"
TYPING_NOTICE = "typing_notice"

OFFLINE_QUEUE = "offline_queue"

ERROR = "error"
