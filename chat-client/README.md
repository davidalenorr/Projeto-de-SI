# Chat — Cliente

Cliente desktop (Tkinter) do chat, com tela de login, lista de contatos e
janela de conversa. Fala com o servidor por sockets TCP, com o canal cifrado
(Diffie-Hellman efêmero + HKDF + AES-256 + HMAC-SHA256) e criptografia ponta
a ponta entre usuários, de forma que o servidor roteie as conversas sem
conseguir ler o conteúdo delas (Projeto 2, seção 8).

## Como executar

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cd client
python main.py [host] [porta]    # padrão: 127.0.0.1 5050
```

No Linux, o Tkinter pode não vir com o Python (`sudo apt install python3-tk`
no Debian/Ubuntu). No macOS e Windows ele já vem com o instalador oficial do
Python.

Abra duas instâncias (dois terminais) com nomes de usuário diferentes para
conversar entre elas, com o servidor do repositório `chat-server` já rodando.

## Arquitetura

Mesmas camadas de baixo do servidor (rede, persistência, segurança), com a
interface do usuário por cima (seção 9.2 do Projeto 2):

```
client/
  main.py                       conecta ao servidor e abre a interface
  protocol.py                   framing e o conjunto de eventos (igual ao do servidor)
  security/
    primitives.py               AES-256-CBC, HMAC-SHA256, HKDF, X25519 (DHE), Ed25519
    channel_session.py          sessão cifrada com o servidor (chaves, expiração)
    e2e_session.py              sessão cifrada com cada contato (chaves, expiração)
    keystore.py                 identidade local (Ed25519) e chave mestra do histórico
  service/
    session_service.py          registro e as duas formas de login (7.2 e 7.3)
    contacts_service.py         lista de contatos e presença
    conversation_service.py     handshake E2E, autenticação mútua, mensagens, digitação
  network/
    connection.py                socket + thread de recepção + thread de envio
  persistence/
    local_db.py                 histórico local, cifrado por campo com AES-256
  gui/
    app.py                      janela principal + barramento de eventos do servidor
    login_screen.py             tela de login e registro
    main_screen.py               lista de contatos e janela de conversa
```

Responsabilidades:
- **`network`**: só fala socket; nunca é chamado pela thread da interface
  diretamente (ela só enfileira o que quer enviar e lê uma fila do que
  chegou). Isso segue a Figura 7 do Projeto 1 e evita a tela travar.
- **`security`**: executa as primitivas e guarda o estado de cada sessão
  cifrada — tanto a do canal com o servidor quanto a de cada contato.
- **`service`**: as regras do chat do ponto de vista do cliente — quando
  pedir a chave pública de alguém, quando autenticar mutuamente, quando
  recusar o envio de uma mensagem por falta de sessão segura.
- **`gui`**: só desenha e responde ao usuário. Não conhece socket nem
  disco: pede tudo aos serviços.

## Decisões de projeto que valem registrar

- **Duas camadas de cifra por mensagem** (seção 8.2): uma mensagem para outro
  usuário é primeiro selada com a chave E2E do par (A, B) e só depois enviada
  como um evento comum, que a camada de rede sela de novo com a chave do
  canal com o servidor. O servidor abre a camada externa e não tem como abrir
  a interna.
- **Assinatura**: o projeto permite RSA ou ECC; foi escolhido Ed25519 (família
  ECC) tanto para o desafio de login (7.2) quanto para a autenticação mútua
  entre usuários (8.3), por ser mais simples e eficiente.
- **Sem chave, sem entrega** (seção 8.4, Figura 12): a checagem "A e B já têm
  chave?" é feita aqui no cliente, não no servidor — e não poderia ser
  diferente, já que o servidor nunca vê as chaves E2E. Se o contato está
  offline e nunca houve handshake com ele, o envio é recusado na hora, com um
  aviso claro na tela.
- **Chave do histórico local** (seção 8.5): não deriva da senha, porque o
  login em um dispositivo já conhecido é, por definição, sem senha (7.2). Em
  vez disso, é uma chave aleatória gerada uma vez por dispositivo e guardada
  com permissão de leitura restrita ao usuário do sistema operacional.
