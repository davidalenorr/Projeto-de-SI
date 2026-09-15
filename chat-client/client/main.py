"""Ponto de entrada do cliente: conecta ao servidor e abre a interface.

Uso: python main.py [host] [porta]
"""
import sys

from gui.app import App
from gui.login_screen import LoginScreen
from gui.main_screen import MainScreen
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

    connection = Connection(host, port)
    connection.start()

    app = App(connection)
    session_service = SessionService(connection, app.events)
    contacts_service = ContactsService(app.events)

    def on_logged_in():
        local_db = LocalDatabase(f"history_{session_service.username}.db", session_service.local_master_key)
        conversation_service = ConversationService(
            connection, app.events, session_service, contacts_service, local_db
        )
        app.show(lambda root: MainScreen(root, app, session_service, contacts_service, conversation_service))

    app.show(lambda root: LoginScreen(root, app, session_service, on_logged_in))
    app.run()


if __name__ == "__main__":
    main()
