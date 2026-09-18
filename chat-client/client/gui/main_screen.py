"""Tela principal: lista de contatos à esquerda, janela de conversa à
direita (Projeto 1, seções 5.3 a 5.9).

A lista de contatos marca com um ícone vermelho quem tem mensagem não lida:
alguém cuja mensagem chegou (em tempo real ou da fila offline, seção 8.4 do
Projeto 2) enquanto a conversa com ele não estava aberta na tela. O marcador
some assim que o usuário seleciona aquele contato.
"""
import tkinter as tk

import protocol

# Círculo vermelho: um emoji renderiza colorido independente da cor do texto
# do item na Listbox, que só permite uma cor de primeiro plano por linha.
_UNREAD_MARK = "\U0001F534"


class MainScreen(tk.Frame):
    def __init__(self, master, app, session_service, contacts_service, conversation_service):
        super().__init__(master)
        self._app = app
        self._session = session_service
        self._contacts = contacts_service
        self._conversation = conversation_service
        self._selected_contact = None
        self._typing_after_id = None
        self._unread_contacts = set()
        self._connection_lost = False

        self._build_widgets()

        app.events.on(protocol.CONTACTS_LIST, lambda e: self._refresh_contacts())
        app.events.on(protocol.PRESENCE_UPDATE, lambda e: self._refresh_contacts())
        self._conversation.message_listeners.append(self._on_message)
        self._conversation.typing_listeners.append(self._on_typing)
        self._conversation.error_listeners.append(self._on_error)
        app.on_connection_lost(self._on_connection_lost)

        self._refresh_contacts()

    def _build_widgets(self):
        left = tk.Frame(self, width=220)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        tk.Label(left, text=f"Logado como {self._session.username}", anchor="w",
                 font=("TkDefaultFont", 10, "bold")).pack(fill="x", padx=8, pady=8)
        self._contact_list = tk.Listbox(left)
        self._contact_list.pack(fill="both", expand=True, padx=8, pady=8)
        self._contact_list.bind("<<ListboxSelect>>", self._on_select_contact)

        right = tk.Frame(self)
        right.pack(side="left", fill="both", expand=True)
        self._offline_banner = tk.Label(
            right, text="Sem conexão com o servidor: histórico local disponível, envio desativado.",
            fg="white", bg="#b00020", anchor="w",
        )
        self._typing_label = tk.Label(right, text="", fg="gray", anchor="w")
        self._typing_label.pack(fill="x", padx=8, pady=(8, 0))
        self._history = tk.Text(right, state="disabled", wrap="word")
        self._history.pack(fill="both", expand=True, padx=8, pady=8)

        entry_frame = tk.Frame(right)
        entry_frame.pack(fill="x", padx=8, pady=(0, 8))
        self._entry = tk.Entry(entry_frame)
        self._entry.pack(side="left", fill="x", expand=True)
        self._entry.bind("<KeyRelease>", self._on_key_release)
        self._entry.bind("<Return>", lambda e: self._send())
        self._send_button = tk.Button(entry_frame, text="Enviar", command=self._send)
        self._send_button.pack(side="left", padx=(8, 0))

    def _refresh_contacts(self):
        self._contact_list.delete(0, tk.END)
        for username in sorted(self._contacts.contacts.keys()):
            if username == self._session.username:
                continue
            status = "online" if self._contacts.is_online(username) else "offline"
            mark = f"{_UNREAD_MARK} " if username in self._unread_contacts else ""
            self._contact_list.insert(tk.END, f"{mark}{username} ({status})")
            if username == self._selected_contact:
                self._contact_list.selection_set(tk.END)

    def _on_select_contact(self, _event):
        selection = self._contact_list.curselection()
        if not selection:
            return
        label = self._contact_list.get(selection[0])
        if label.startswith(_UNREAD_MARK):
            label = label[len(_UNREAD_MARK) + 1:]
        username = label.rsplit(" (", 1)[0]
        self._selected_contact = username
        self._unread_contacts.discard(username)
        self._refresh_contacts()
        self._typing_label.config(text="")
        self._load_history(username)
        self._conversation.ensure_session(username)

    def _load_history(self, contact):
        self._history.config(state="normal")
        self._history.delete("1.0", tk.END)
        for item in self._conversation.history_with(contact):
            who = "Você" if item["direction"] == "sent" else contact
            self._history.insert(tk.END, f"{who}: {item['text']}\n")
        self._history.config(state="disabled")
        self._history.see(tk.END)

    def _on_connection_lost(self):
        self._connection_lost = True
        self._offline_banner.pack(fill="x", padx=8, pady=(8, 0), before=self._typing_label)
        self._entry.config(state="disabled")
        self._send_button.config(state="disabled")

    def _send(self):
        if self._connection_lost or not self._selected_contact:
            return
        text = self._entry.get().strip()
        if not text:
            return
        self._entry.delete(0, tk.END)
        self._conversation.send_typing(self._selected_contact, False)
        self._conversation.send_message(self._selected_contact, text)

    def _on_key_release(self, _event):
        if not self._selected_contact:
            return
        self._conversation.send_typing(self._selected_contact, True)
        if self._typing_after_id:
            self.after_cancel(self._typing_after_id)
        self._typing_after_id = self.after(
            2000, lambda: self._conversation.send_typing(self._selected_contact, False)
        )

    def _on_message(self, contact, direction, text, _timestamp):
        if contact == self._selected_contact:
            who = "Você" if direction == "sent" else contact
            self._history.config(state="normal")
            self._history.insert(tk.END, f"{who}: {text}\n")
            self._history.config(state="disabled")
            self._history.see(tk.END)
        elif direction == "received":
            self._unread_contacts.add(contact)
            self._refresh_contacts()

    def _on_typing(self, contact, active):
        if contact == self._selected_contact:
            self._typing_label.config(text=f"{contact} está digitando..." if active else "")

    def _on_error(self, message):
        self._app.show_error(message)
