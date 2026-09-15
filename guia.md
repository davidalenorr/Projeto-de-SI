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

Abre uma janela. Na aba **Registrar**, cria um usuário e senha. Depois vai na aba **Entrar**, digita o mesmo usuário e clica em Entrar.

## 3. Para conversar, precisa de dois usuários

Abre um **terceiro terminal**, ativa o mesmo venv do cliente (`source chat-client/.venv/bin/activate`) e roda `python main.py` de novo (de dentro de `chat-client/client`). Registra um segundo usuário nessa segunda janela.

Com os dois logados ao mesmo tempo, cada um aparece na lista de contatos do outro como "online". Clica no nome do contato e manda mensagem.

## Se for testar em máquinas diferentes

No cliente, passa o IP do servidor:

```bash
python main.py 192.168.0.10 5050
```

(IP e porta da máquina onde o servidor está rodando.)

## Erros comuns

- **`ModuleNotFoundError`**: esqueceu de ativar o venv (`source .venv/bin/activate`) ou de rodar `pip install -r requirements.txt`.
- **Tkinter não abre / erro de `tkinter`**: no Linux, instala com `sudo apt install python3-tk`.
- **`Address already in use`** ao subir o servidor: já tem um servidor rodando nessa porta. Mata o processo antigo ou usa outra porta (`python main.py 5051`, e no cliente aponta pra essa porta também).
- **Login pede senha de novo mesmo já tendo registrado**: é o comportamento esperado se for a primeira vez que esse computador loga com esse usuário (dispositivo novo). Da segunda vez em diante, ele reconhece o dispositivo e não pede senha.
