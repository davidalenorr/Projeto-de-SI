"""Tela mostrada quando o cliente não conseguiu (ou deixou de conseguir) se
conectar ao servidor.

O app não trava nem fecha nesse caso. Em vez de exigir rede para tudo, esta
tela lista as identidades já conhecidas neste dispositivo (quem já logou
aqui antes, seção 7.2) e permite abrir o histórico local de cada uma em modo
somente leitura (`OfflineMainScreen`), sem depender do servidor: a chave que
cifra o histórico (seção 8.5) já vive só neste dispositivo, então nada disso
precisa de rede.
"""
import tkinter as tk

from gui.offline_main_screen import OfflineMainScreen
from persistence.local_db import LocalDatabase
from security import keystore


class OfflineScreen(tk.Frame):
    def __init__(self, master, app, on_retry, reason=None):
        super().__init__(master)
        self._app = app
        self._on_retry = on_retry

        tk.Label(
            self, text="Sem conexão com o servidor",
            font=("TkDefaultFont", 12, "bold"), fg="red",
        ).pack(pady=(24, 6))
        if reason:
            tk.Label(self, text=reason, wraplength=420, fg="gray").pack(pady=(0, 10))
        tk.Label(
            self,
            text="Você ainda pode consultar o histórico já salvo neste dispositivo. "
                 "Não é possível enviar mensagens novas sem conexão.",
            wraplength=420, justify="center",
        ).pack(pady=(0, 16))

        usernames = keystore.list_known_usernames()
        if usernames:
            tk.Label(self, text="Abrir histórico de:").pack()
            listbox = tk.Listbox(self, height=6, width=30)
            for username in usernames:
                listbox.insert(tk.END, username)
            listbox.pack(pady=6)

            def open_selected():
                selection = listbox.curselection()
                if not selection:
                    return
                self._open_offline_history(listbox.get(selection[0]))

            listbox.bind("<Double-Button-1>", lambda _e: open_selected())
            tk.Button(self, text="Ver mensagens offline", command=open_selected).pack(pady=4)
        else:
            tk.Label(
                self, text="Nenhuma identidade local encontrada neste dispositivo.", fg="gray",
            ).pack(pady=4)

        tk.Button(self, text="Tentar reconectar", command=self._on_retry).pack(pady=20)

    def _open_offline_history(self, username: str) -> None:
        local_master_key = keystore.load_or_create_local_master_key(username)
        local_db = LocalDatabase(f"history_{username}.db", local_master_key)
        self._app.show(
            lambda root: OfflineMainScreen(root, self._app, username, local_db, self._on_retry)
        )
