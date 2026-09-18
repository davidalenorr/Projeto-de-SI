"""Aplicação Tkinter: o roteador de eventos do servidor e a troca de telas.

Toda comunicação com o servidor chega aqui como eventos numa fila (a thread
de recepção do socket nunca toca a interface diretamente, ver
network/connection.py). O poll() roda dentro do loop do Tkinter e é o único
lugar do programa que lê essa fila — daí para frente, tudo acontece na thread
da interface, sem risco de condição de corrida na tela.
"""
import queue
import tkinter as tk
from tkinter import messagebox


class AppEvents:
    """Um pub/sub simples: cada camada de serviço se inscreve nos eventos que
    lhe interessam, sem precisar conhecer quem mais está ouvindo."""

    def __init__(self):
        self._listeners = {}

    def on(self, event_type, callback):
        self._listeners.setdefault(event_type, []).append(callback)

    def dispatch(self, event: dict):
        for cb in list(self._listeners.get(event.get("type"), [])):
            cb(event)


class App:
    def __init__(self, connection=None):
        self.root = tk.Tk()
        self.root.title("Chat seguro")
        self.root.geometry("820x560")
        self.connection = connection
        self.events = AppEvents()
        self._current_frame = None
        self._connection_lost_handler = None
        self.root.after(100, self._poll)

    def on_connection_lost(self, callback) -> None:
        """Define quem reage quando o socket com o servidor cai, além do
        aviso padrão (usado pela tela atual para desabilitar o envio).
        Substitui o handler anterior: só a tela em exibição deve reagir."""
        self._connection_lost_handler = callback

    def _poll(self):
        if self.connection is not None:
            while True:
                try:
                    event = self.connection.inbox.get_nowait()
                except queue.Empty:
                    break
                if event.get("type") == "connection_lost":
                    self.show_error("A conexão com o servidor foi perdida.")
                    if self._connection_lost_handler:
                        self._connection_lost_handler()
                else:
                    self.events.dispatch(event)
        self.root.after(100, self._poll)

    def show(self, frame_factory) -> None:
        if self._current_frame is not None:
            self._current_frame.destroy()
        self._connection_lost_handler = None
        self._current_frame = frame_factory(self.root)
        self._current_frame.pack(fill="both", expand=True)

    def show_error(self, message: str) -> None:
        messagebox.showerror("Erro", message)

    def run(self) -> None:
        self.root.mainloop()
