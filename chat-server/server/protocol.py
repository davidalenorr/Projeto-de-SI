"""Formato do pacote trocado entre cliente e servidor.

Framing: 4 bytes (big-endian, uint32) com o tamanho do payload, seguidos do
payload em JSON (UTF-8). Vale tanto para o handshake inicial (em claro, só
acontece uma vez por conexão) quanto para os pacotes do tipo "secure", cujo
conteúdo é um envelope { iv, ciphertext, mac } cifrado com AES e autenticado
com HMAC (ver security/primitives.py).
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


# ---- Tipos de evento do protocolo (o "verbo" de cada mensagem) ----
# O conjunto abaixo cobre a tabela da seção 5.10 do Projeto 1 e os eventos de
# segurança acrescentados pelo Projeto 2 (handshake do canal, handshake e
# autenticação ponta a ponta entre usuários, troca de dispositivo).

CHANNEL_HELLO = "channel_hello"
CHANNEL_HELLO_ACK = "channel_hello_ack"
CHANNEL_REKEY = "channel_rekey"
CHANNEL_REKEY_ACK = "channel_rekey_ack"
SECURE = "secure"

REGISTER = "register"
REGISTER_RESPONSE = "register_response"

LOGIN_DEVICE = "login_device"              # dispositivo já autenticado antes (7.2)
LOGIN_NEW_DEVICE = "login_new_device"      # dispositivo novo, com senha (7.3)
LOGIN_CHALLENGE = "login_challenge"
LOGIN_CHALLENGE_RESPONSE = "login_challenge_response"
LOGIN_RESPONSE = "login_response"

CONTACTS_LIST = "contacts_list"
PRESENCE_UPDATE = "presence_update"

PUBKEY_REQUEST = "pubkey_request"
PUBKEY_RESPONSE = "pubkey_response"
PEER_INCOMING_KEY = "peer_incoming_key"    # servidor avisa B que A vai iniciar handshake (7.4)
KEY_CHANGED_NOTICE = "key_changed_notice"

PEER_HANDSHAKE_INIT = "peer_handshake_init"
PEER_HANDSHAKE_ACK = "peer_handshake_ack"
PEER_FRAME = "peer_frame"                  # carrega um envelope E2E opaco (autenticação ou mensagem)

TYPING_START = "typing_start"
TYPING_STOP = "typing_stop"
TYPING_NOTICE = "typing_notice"

OFFLINE_QUEUE = "offline_queue"

ERROR = "error"
