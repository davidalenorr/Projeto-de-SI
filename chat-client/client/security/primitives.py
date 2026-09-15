"""Primitivas criptográficas usadas no canal cliente-servidor e na E2EE entre
usuários (Projeto 2, seções 5 e 6). Idêntico ao módulo equivalente do
servidor — os dois lados de cada handshake precisam executar exatamente as
mesmas contas.

Escolhas fixadas aqui, usadas no projeto inteiro:
- Diffie-Hellman efêmero: X25519 (família ECC), por eficiência.
- Derivação de chaves: HKDF-SHA256, saída de 64 bytes -> chave AES (32 bytes)
  + chave HMAC (32 bytes), como a Figura 3 do Projeto 2 descreve.
- Cifra simétrica: AES-256-CBC com padding PKCS7 e IV aleatório de 16 bytes
  por mensagem.
- Integridade/autenticidade: HMAC-SHA256 sobre (IV || texto cifrado) —
  Encrypt-then-MAC, na ordem exigida pela seção 6.3.
- Identidade de usuário: Ed25519 (uma das duas famílias ECC/RSA permitidas),
  usada tanto no desafio de login quanto na autenticação mútua entre usuários.
"""
import base64
import hmac as hmac_module
import os

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import (
    Encoding, NoEncryption, PrivateFormat, PublicFormat,
)

AES_KEY_LEN = 32
HMAC_KEY_LEN = 32
IV_LEN = 16


class IntegrityError(Exception):
    """O HMAC recebido não confere: mensagem alterada, chave errada ou
    tentativa de adulteração. Descartada sem ser decifrada (seção 6.3)."""


def b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def b64d(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


# ---- Diffie-Hellman efêmero (X25519) ----

def generate_dh_keypair():
    private_key = x25519.X25519PrivateKey.generate()
    public_bytes = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return private_key, public_bytes


def dh_shared_secret(private_key: x25519.X25519PrivateKey, peer_public_bytes: bytes) -> bytes:
    peer_public = x25519.X25519PublicKey.from_public_bytes(peer_public_bytes)
    return private_key.exchange(peer_public)


def generate_salt(length: int = 16) -> bytes:
    return os.urandom(length)


# ---- HKDF: chave da sessão + salt -> chave 1 (AES) e chave 2 (HMAC) ----

def derive_session_keys(shared_secret: bytes, salt: bytes, info: bytes = b"chat-session") -> tuple:
    hkdf = HKDF(algorithm=hashes.SHA256(), length=AES_KEY_LEN + HMAC_KEY_LEN, salt=salt, info=info)
    material = hkdf.derive(shared_secret)
    return material[:AES_KEY_LEN], material[AES_KEY_LEN:]


# ---- AES-256-CBC ----

def aes_encrypt(key: bytes, plaintext: bytes) -> tuple:
    iv = os.urandom(IV_LEN)
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded = padder.update(plaintext) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return iv, ciphertext


def aes_decrypt(key: bytes, iv: bytes, ciphertext: bytes) -> bytes:
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    return unpadder.update(padded) + unpadder.finalize()


# ---- HMAC-SHA256 ----

def hmac_sign(key: bytes, data: bytes) -> bytes:
    return hmac_module.new(key, data, "sha256").digest()


def hmac_verify(key: bytes, data: bytes, mac: bytes) -> bool:
    return hmac_module.compare_digest(hmac_sign(key, data), mac)


# ---- Encrypt-then-MAC: seal / open de um envelope { iv, ciphertext, mac } ----

def seal(key_aes: bytes, key_hmac: bytes, plaintext: bytes) -> dict:
    iv, ciphertext = aes_encrypt(key_aes, plaintext)
    mac = hmac_sign(key_hmac, iv + ciphertext)
    return {"iv": b64e(iv), "ciphertext": b64e(ciphertext), "mac": b64e(mac)}


def open_sealed(key_aes: bytes, key_hmac: bytes, envelope: dict) -> bytes:
    iv = b64d(envelope["iv"])
    ciphertext = b64d(envelope["ciphertext"])
    mac = b64d(envelope["mac"])
    if not hmac_verify(key_hmac, iv + ciphertext, mac):
        raise IntegrityError("MAC inválido: mensagem descartada")
    return aes_decrypt(key_aes, iv, ciphertext)


# ---- Identidade e assinatura digital (Ed25519) ----

def generate_identity_keypair():
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_bytes = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return private_key, public_bytes


def identity_private_key_from_bytes(raw: bytes) -> ed25519.Ed25519PrivateKey:
    return ed25519.Ed25519PrivateKey.from_private_bytes(raw)


def identity_private_key_to_bytes(private_key: ed25519.Ed25519PrivateKey) -> bytes:
    return private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())


def sign(private_key: ed25519.Ed25519PrivateKey, data: bytes) -> bytes:
    return private_key.sign(data)


def verify_signature(public_key_bytes: bytes, data: bytes, signature: bytes) -> bool:
    try:
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
        public_key.verify(signature, data)
        return True
    except InvalidSignature:
        return False
