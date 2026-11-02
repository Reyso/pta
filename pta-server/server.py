import os
import select
import socket
from pathlib import Path


HOST = "0.0.0.0"
PORT = 11550
REQUEST_WAIT = 0.1
POLL_INTERVAL = 0.2
BASE_DIR = Path(__file__).resolve().parent


def load_users():
    with (BASE_DIR / "users.txt").open(encoding="ascii") as file:
        return {line.strip() for line in file if line.strip()}


def receive_request(connection):
    while not select.select([connection], [], [], POLL_INTERVAL)[0]:
        continue

    data = bytearray(connection.recv(4096))

    if not data:
        return b""

    # O cliente original não envia um delimitador no fim do pedido.
    while select.select([connection], [], [], REQUEST_WAIT)[0]:
        chunk = connection.recv(4096)
        if not chunk:
            break
        data.extend(chunk)

    return bytes(data)


def request_sequence(data):
    sequence = data.split(b" ", 1)[0]
    return sequence.decode("ascii") if sequence.isdigit() else "0"


def parse_request(data):
    try:
        parts = data.decode("ascii").split(" ")
    except UnicodeDecodeError:
        return None

    if len(parts) < 2 or not parts[0].isdigit() or any(not part for part in parts):
        return None

    sequence = parts[0]
    command = parts[1]
    arguments = parts[2:]

    return sequence, command, arguments


def send_reply(connection, sequence, reply):
    message = f"{sequence} {reply}"
    connection.sendall(message.encode("ascii"))


def list_files(connection, sequence):
    try:
        names = sorted(path.name for path in (BASE_DIR / "files").iterdir() if path.is_file())
        reply = f"ARQS {len(names)} {','.join(names)}"
        reply.encode("ascii")
    except (OSError, UnicodeEncodeError):
        send_reply(connection, sequence, "NOK")
        return

    send_reply(connection, sequence, reply)


def send_file(connection, sequence, name):
    try:
        directory = (BASE_DIR / "files").resolve()
        path = (directory / name).resolve()

        if path.parent != directory or not path.is_file():
            send_reply(connection, sequence, "NOK")
            return

        file = path.open("rb")
    except (OSError, ValueError):
        send_reply(connection, sequence, "NOK")
        return

    with file:
        try:
            size = os.fstat(file.fileno()).st_size
            chunk = file.read(4096)
        except OSError:
            send_reply(connection, sequence, "NOK")
            return

        header = f"{sequence} ARQ {size} ".encode("ascii")
        connection.sendall(header + chunk)

        while chunk:
            chunk = file.read(4096)
            if chunk:
                connection.sendall(chunk)


def handle_client(connection, users):
    authenticated = False

    while True:
        data = receive_request(connection)

        if not data:
            return

        request = parse_request(data)

        if request is None:
            send_reply(connection, request_sequence(data), "NOK")
            if not authenticated:
                return
            continue

        sequence, command, arguments = request

        if not authenticated:
            if command != "CUMP" or len(arguments) != 1 or arguments[0] not in users:
                send_reply(connection, sequence, "NOK")
                return

            send_reply(connection, sequence, "OK")
            authenticated = True
            continue

        if command == "LIST" and not arguments:
            list_files(connection, sequence)
            continue

        if command == "PEGA" and len(arguments) == 1 and arguments[0]:
            send_file(connection, sequence, arguments[0])
            continue

        if command == "TERM" and not arguments:
            send_reply(connection, sequence, "OK")
            return

        send_reply(connection, sequence, "NOK")


def main():
    users = load_users()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen()

        print(f"Servidor PTA ouvindo na porta {PORT}", flush=True)

        while True:
            if not select.select([server], [], [], POLL_INTERVAL)[0]:
                continue

            connection, address = server.accept()
            print(f"Conexão de {address[0]}:{address[1]}", flush=True)

            with connection:
                try:
                    handle_client(connection, users)
                except ConnectionError:
                    print("O cliente interrompeu a conexão.", flush=True)
                except OSError as error:
                    print(f"Erro ao atender o cliente: {error}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
