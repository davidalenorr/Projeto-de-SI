"""Ponto de entrada do servidor: monta as camadas e começa a escutar.

Uso: python main.py [porta]
"""
import sys

from db import Database
from network.client_registry import ClientRegistry
from network.server_socket import ChatServer
from service.auth_service import AuthService
from service.chat_service import ChatService

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 5050


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    db = Database("server_data.db")
    registry = ClientRegistry()
    auth_service = AuthService(db)
    chat_service = ChatService(db, registry)
    server = ChatServer(DEFAULT_HOST, port, auth_service, chat_service, registry)
    server.serve_forever()


if __name__ == "__main__":
    main()
