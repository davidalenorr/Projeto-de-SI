"""Ponto de entrada do cliente: conecta ao servidor e abre a interface.

Se o servidor estiver inacessível na inicialização, ou a conexão cair
durante o uso, o programa não trava nem fecha: cai para o modo offline
(`gui/offline_screen.py`), que ainda permite consultar o histórico local já
salvo neste dispositivo (seção 8.5 do Projeto 2). Um botão "Tentar
reconectar" refaz a tentativa a qualquer momento.

Uso: python main.py [host] [porta]
"""
import socket
import sys

import protocol
from gui.app import App
from gui.login_screen import LoginScreen
from gui.main_screen import MainScreen
from gui.offline_screen import OfflineScreen
from network.connection import Connection
from persistence.local_db import LocalDatabase
from service.contacts_service import ContactsService
from service.conversation_service import ConversationService
from service.session_service import SessionService

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5050


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HOST
    port = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_PORT

    app = App()

    def start_online_session(connection):
        app.connection = connection
        session_service = SessionService(connection, app.events)
        contacts_service = ContactsService(app.events)

        def on_logged_in():
            local_db = LocalDatabase(f"history_{session_service.username}.db", session_service.local_master_key)
            conversation_service = ConversationService(
                connection, app.events, session_service, contacts_service, local_db
            )
            app.show(lambda root: MainScreen(root, app, session_service, contacts_service, conversation_service))

        app.show(lambda root: LoginScreen(root, app, session_service, on_logged_in))

    def try_connect():
        try:
            connection = Connection(host, port)
            connection.start()
        except (OSError, protocol.ConnectionClosed) as exc:
            app.show(lambda root: OfflineScreen(root, app, on_retry=try_connect, reason=str(exc)))
            return
        start_online_session(connection)

    try_connect()
    app.run()


if __name__ == "__main__":
    main()
