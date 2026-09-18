"""Tela de login e registro (Projeto 1, seções 5.1-5.2; Projeto 2, seções
7.1-7.3).

Na aba "Entrar", a senha é sempre exigida. Se este dispositivo já tem uma
identidade local para o usuário informado, a senha é conferida no servidor e,
por cima dela, o dispositivo ainda prova sua posse por desafio assinado
(7.2). Caso contrário, é o caso de um dispositivo novo (7.3), que registra a
nova chave pública a partir da mesma senha.
"""
import tkinter as tk
from tkinter import ttk

import protocol


class LoginScreen(tk.Frame):
    def __init__(self, master, app, session_service, on_logged_in):
        super().__init__(master)
        self._app = app
        self._session_service = session_service
        self._on_logged_in = on_logged_in

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=20, pady=20)
        notebook.add(self._build_login_tab(notebook), text="Entrar")
        notebook.add(self._build_register_tab(notebook), text="Registrar")

        app.events.on(protocol.LOGIN_RESPONSE, self._on_login_response)
        app.events.on(protocol.REGISTER_RESPONSE, self._on_register_response)

    def _build_login_tab(self, parent):
        frame = tk.Frame(parent)

        tk.Label(frame, text="Usuário").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        username_entry = tk.Entry(frame)
        username_entry.grid(row=0, column=1, padx=10, pady=5)

        tk.Label(frame, text="Senha").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        password_entry = tk.Entry(frame, show="*")
        password_entry.grid(row=1, column=1, padx=10, pady=5)
        status_label = tk.Label(frame, text="", fg="red", wraplength=280, justify="left")
        status_label.grid(row=2, column=0, columnspan=2, padx=10)

        def submit():
            username = username_entry.get().strip()
            password = password_entry.get()
            if not username or not password:
                return
            if self._session_service.is_known_device(username):
                self._session_service.login_known_device(username, password)
                status_label.config(fg="black", text="Autenticando com este dispositivo...")
            else:
                self._session_service.login_new_device(username, password)
                status_label.config(fg="black", text="Autenticando...")

        tk.Button(frame, text="Entrar", command=submit).grid(row=3, column=0, columnspan=2, pady=10)
        self._login_status_label = status_label
        return frame

    def _build_register_tab(self, parent):
        frame = tk.Frame(parent)
        tk.Label(frame, text="Usuário").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        username_entry = tk.Entry(frame)
        username_entry.grid(row=0, column=1, padx=10, pady=5)
        tk.Label(frame, text="Senha").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        password_entry = tk.Entry(frame, show="*")
        password_entry.grid(row=1, column=1, padx=10, pady=5)
        status_label = tk.Label(frame, text="", fg="red", wraplength=280, justify="left")
        status_label.grid(row=3, column=0, columnspan=2, padx=10)

        def submit():
            username = username_entry.get().strip()
            password = password_entry.get()
            if not username or not password:
                return
            self._session_service.register(username, password)
            status_label.config(fg="black", text="Registrando...")

        tk.Button(frame, text="Registrar", command=submit).grid(row=2, column=0, columnspan=2, pady=10)
        self._register_status_label = status_label
        return frame

    def _on_login_response(self, event):
        if event["success"]:
            self._session_service.finish_login()
            self._on_logged_in()
        else:
            self._login_status_label.config(fg="red", text=event.get("reason") or "falha no login")

    def _on_register_response(self, event):
        if event["success"]:
            self._register_status_label.config(fg="green", text="Registrado com sucesso! Vá para a aba Entrar.")
        else:
            self._register_status_label.config(fg="red", text=event.get("reason") or "falha no registro")
