# Chat — Servidor

Servidor TCP/IP multithread do chat, com o canal cliente-servidor cifrado
conforme o Projeto 2 (Diffie-Hellman efêmero + HKDF + AES-256 + HMAC-SHA256),
registro/login com Argon2 e assinatura digital Ed25519.

## Como executar

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cd server
python main.py [porta]           # porta padrão: 5050
```

O banco `server_data.db` (SQLite) é criado automaticamente no diretório onde
o comando é executado.

## Arquitetura

Duas camadas de infraestrutura (rede e persistência) não se conhecem entre
si; quem decide o que usar é a camada de serviço/domínio, com a segurança
entrando como uma camada própria entre as duas (seção 9.1 do Projeto 2):

```
server/
  main.py                    monta as camadas e inicia o servidor
  protocol.py                framing (length-prefixed JSON) e o conjunto de eventos
  db.py                      persistência: usuários e fila de mensagens offline (SQLite)
  security/
    primitives.py            AES-256-CBC, HMAC-SHA256, HKDF, X25519 (DHE), Ed25519, Argon2
    channel_session.py       estado da sessão cifrada com um cliente (chaves, expiração)
  service/
    auth_service.py          registro, login por senha (Argon2), login por desafio assinado
    chat_service.py          contatos, presença, roteamento de mensagens, fila offline
  network/
    server_socket.py         thread de escuta + uma thread por cliente conectado
    client_registry.py       quem está online agora (acesso thread-safe)
```

Responsabilidades:
- **`network`**: só fala socket. Não conhece regra de negócio nenhuma.
- **`security`**: executa as primitivas e guarda o estado de cada sessão
  cifrada. Não decide quando renovar (isso é o cliente quem inicia).
- **`service`**: as regras do chat — quem pode se registrar, para quem
  encaminhar uma mensagem, quando guardar na fila offline.
- **`db`**: única peça que toca o SQLite.

## O que o servidor nunca vê

O servidor decifra apenas a camada do **canal** (dele com cada cliente). O
conteúdo de uma mensagem entre dois usuários chega a ele já cifrado com uma
segunda camada, negociada só entre os dois usuários (ponta a ponta); o
servidor decifra a camada externa, mas repassa o "peer_frame" interno sem
conseguir abri-lo — inclusive quando precisa guardá-lo na fila offline.
