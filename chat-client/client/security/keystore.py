"""Guarda, por usuário, a identidade local (par Ed25519) e a chave mestra
local usada para cifrar o histórico (seção 8.5).

A chave mestra local NÃO deriva da senha: o login em "dispositivo já
autenticado" (seção 7.2) é, por definição, sem senha, então algo precisa
proteger o histórico local sem exigir uma senha a cada abertura do app. Em
vez disso, essa chave vive num arquivo com permissão restrita ao dono do
processo — o que modela "só este dispositivo conhece esta chave". A senha
continua sendo o que autentica o usuário perante o SERVIDOR (registro e troca
de dispositivo); são preocupações diferentes.
"""
import base64
import json
import os
import stat

from security import primitives

DATA_DIR = os.path.join(os.path.expanduser("~"), ".chat_client")


def _user_dir(username: str) -> str:
    path = os.path.join(DATA_DIR, username)
    os.makedirs(path, exist_ok=True)
    return path


def has_identity(username: str) -> bool:
    return os.path.exists(os.path.join(_user_dir(username), "identity.json"))


def list_known_usernames():
    """Usuários com identidade local neste dispositivo, usado pela tela
    offline para saber de quem dá para abrir o histórico sem servidor."""
    if not os.path.isdir(DATA_DIR):
        return []
    return sorted(
        name for name in os.listdir(DATA_DIR)
        if os.path.exists(os.path.join(DATA_DIR, name, "identity.json"))
    )


def create_identity(username: str):
    private_key, public_key_bytes = primitives.generate_identity_keypair()
    private_bytes = primitives.identity_private_key_to_bytes(private_key)
    _save_identity(username, private_bytes, public_key_bytes)
    return private_key, public_key_bytes


def load_identity(username: str):
    path = os.path.join(_user_dir(username), "identity.json")
    with open(path, "r") as f:
        data = json.load(f)
    private_key = primitives.identity_private_key_from_bytes(base64.b64decode(data["private_key"]))
    public_key_bytes = base64.b64decode(data["public_key"])
    return private_key, public_key_bytes


def _save_identity(username: str, private_bytes: bytes, public_key_bytes: bytes):
    path = os.path.join(_user_dir(username), "identity.json")
    with open(path, "w") as f:
        json.dump({
            "private_key": base64.b64encode(private_bytes).decode("ascii"),
            "public_key": base64.b64encode(public_key_bytes).decode("ascii"),
        }, f)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def load_or_create_local_master_key(username: str) -> bytes:
    path = os.path.join(_user_dir(username), "local.key")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    key = os.urandom(32)
    with open(path, "wb") as f:
        f.write(key)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    return key
