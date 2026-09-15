"""Mantém a lista de contatos e a presença de cada um (Projeto 1, seções 5.3
e 5.7)."""
import protocol


class ContactsService:
    def __init__(self, app_events):
        self._events = app_events
        self.contacts = {}  # username -> online (bool)

        self._events.on(protocol.CONTACTS_LIST, self._on_list)
        self._events.on(protocol.PRESENCE_UPDATE, self._on_presence)

    def _on_list(self, event):
        self.contacts = {c["username"]: c["online"] for c in event["contacts"]}

    def _on_presence(self, event):
        self.contacts[event["username"]] = event["online"]

    def is_online(self, username: str) -> bool:
        return self.contacts.get(username, False)
