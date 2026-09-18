"""Tela principal em modo offline: mesma ideia da `MainScreen`, mas somente
leitura e sem servidor.

Os contatos vêm do próprio histórico local (`LocalDatabase.list_contacts`),
não de uma lista de presença — sem servidor não há como saber quem existe ou
quem está online. Não há envio, digitação nem handshake E2E aqui: é só a
consulta ao que já foi salvo em disco enquanto havia conexão.
"""
import tkinter as tk


class OfflineMainScreen(tk.Frame):
    def __init__(self, master, app, username, local_db, on_retry):
        super().__init__(master)
        self._app = app
        self._local_db = local_db
        self._on_retry = on_retry

        left = tk.Frame(self, width=220)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        tk.Label(
            left, text=f"{username} (offline)", anchor="w",
            font=("TkDefaultFont", 10, "bold"), fg="red",
        ).pack(fill="x", padx=8, pady=8)
        tk.Button(left, text="Tentar reconectar", command=self._on_retry).pack(fill="x", padx=8)
        self._contact_list = tk.Listbox(left)
        self._contact_list.pack(fill="both", expand=True, padx=8, pady=8)
        self._contact_list.bind("<<ListboxSelect>>", self._on_select_contact)

        right = tk.Frame(self)
        right.pack(side="left", fill="both", expand=True)
        tk.Label(
            right, text="Modo offline: somente leitura do histórico salvo neste dispositivo.",
            fg="gray", anchor="w", wraplength=560, justify="left",
        ).pack(fill="x", padx=8, pady=(8, 0))
        self._history = tk.Text(right, state="disabled", wrap="word")
        self._history.pack(fill="both", expand=True, padx=8, pady=8)

        contacts = local_db.list_contacts()
        for contact in contacts:
            self._contact_list.insert(tk.END, contact)
        if not contacts:
            self._history.config(state="normal")
            self._history.insert(tk.END, "Nenhuma conversa salva neste dispositivo ainda.")
            self._history.config(state="disabled")

    def _on_select_contact(self, _event):
        selection = self._contact_list.curselection()
        if not selection:
            return
        contact = self._contact_list.get(selection[0])
        self._history.config(state="normal")
        self._history.delete("1.0", tk.END)
        for item in self._local_db.history_with(contact):
            who = "Você" if item["direction"] == "sent" else contact
            self._history.insert(tk.END, f"{who}: {item['text']}\n")
        self._history.config(state="disabled")
        self._history.see(tk.END)
