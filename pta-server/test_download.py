import hashlib
import socket
from pathlib import Path


def receive_exactly(connection, size):
    data = bytearray()

    while len(data) < size:
        chunk = connection.recv(min(4096, size - len(data)))
        if not chunk:
            raise ConnectionError("A conexão terminou antes da resposta completa.")
        data.extend(chunk)

    return bytes(data)


def receive_field(connection):
    field = bytearray()

    while True:
        byte = receive_exactly(connection, 1)
        if byte == b" ":
            return bytes(field)
        field.extend(byte)


def main(host="127.0.0.1", port=11550):
    directory = Path(__file__).resolve().parent / "files"

    with socket.create_connection((host, port), timeout=5) as connection:
        connection.sendall(b"0 CUMP user1")
        if receive_exactly(connection, 4) != b"0 OK":
            raise ValueError("O servidor não aceitou user1.")

        sequence = 0

        for sequence, path in enumerate(sorted(directory.iterdir()), start=1):
            if not path.is_file():
                continue

            connection.sendall(f"{sequence} PEGA {path.name}".encode("ascii"))
            if receive_field(connection) != str(sequence).encode("ascii"):
                raise ValueError("Número de sequência incorreto.")
            if receive_exactly(connection, 4) != b"ARQ ":
                raise ValueError(f"O servidor não enviou {path.name}.")

            size = int(receive_field(connection))
            content = receive_exactly(connection, size)
            expected = path.read_bytes()

            if size != len(expected) or hashlib.sha256(content).digest() != hashlib.sha256(expected).digest():
                raise ValueError(f"Conteúdo diferente: {path.name}")

            print(f"OK: {path.name} ({size} bytes)")

        sequence += 1
        connection.sendall(f"{sequence} TERM".encode("ascii"))
        expected = f"{sequence} OK".encode("ascii")
        if receive_exactly(connection, len(expected)) != expected:
            raise ValueError("Resposta incorreta ao TERM.")
        if connection.recv(1):
            raise ValueError("Dados inesperados após TERM.")

    print("Todos os arquivos foram recebidos corretamente.")


if __name__ == "__main__":
    main()
