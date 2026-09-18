# Como rodar o projeto

São dois programas: o servidor (`chat-server`) e o cliente (`chat-client`). Precisa dos dois rodando para testar.

## 1. Servidor (abra um terminal)

```bash
cd chat-server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd server
python main.py
```

Deixa esse terminal aberto rodando. Ele escuta na porta 5050.

## 2. Cliente (abra outro terminal)

```bash
cd chat-client
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd client
python main.py
```

## Se for testar em máquinas diferentes

No cliente, passa o IP do servidor:

```bash
python main.py ip do server
```



