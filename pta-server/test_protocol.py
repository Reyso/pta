import socket
import time
import unittest
from pathlib import Path

from test_download import receive_exactly, receive_field


HOST = "127.0.0.1"
PORT = 11550


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.connection = socket.create_connection((HOST, PORT), timeout=5)
        self.addCleanup(self.connection.close)

    def exchange(self, request, expected):
        self.connection.sendall(request)
        self.assertEqual(receive_exactly(self.connection, len(expected)), expected)

    def authenticate(self):
        self.exchange(b"10 CUMP user1", b"10 OK")

    def finish(self, sequence):
        self.exchange(f"{sequence} TERM".encode("ascii"), f"{sequence} OK".encode("ascii"))
        self.assertEqual(self.connection.recv(1), b"")

    def test_command_before_presentation(self):
        self.exchange(b"10 LIST", b"10 NOK")
        self.assertEqual(self.connection.recv(1), b"")

    def test_unknown_user(self):
        self.exchange(b"10 CUMP nonexistent", b"10 NOK")
        self.assertEqual(self.connection.recv(1), b"")

    def test_user_is_case_sensitive(self):
        self.exchange(b"10 CUMP User1", b"10 NOK")
        self.assertEqual(self.connection.recv(1), b"")

    def test_missing_user(self):
        self.exchange(b"10 CUMP", b"10 NOK")
        self.assertEqual(self.connection.recv(1), b"")

    def test_invalid_commands_keep_connection_open(self):
        self.authenticate()
        requests = [b"TRAP", b"CUMP user1", b"LIST extra", b"PEGA", b"PEGA a b", b"TERM extra"]

        for sequence, request in enumerate(requests, start=11):
            with self.subTest(request=request):
                self.exchange(str(sequence).encode() + b" " + request, f"{sequence} NOK".encode())

        self.finish(17)

    def test_malformed_messages(self):
        self.authenticate()
        self.exchange(b"11  LIST", b"11 NOK")
        self.exchange(b"12 PEGA \xff", b"12 NOK")
        self.exchange(b"13 LIST ", b"13 NOK")
        self.exchange(b"invalid LIST", b"0 NOK")
        self.finish(14)

    def test_unavailable_files(self):
        self.authenticate()
        names = ["nonexistent.txt", "../users.txt", "..", "../files"]

        for sequence, name in enumerate(names, start=11):
            with self.subTest(name=name):
                self.exchange(f"{sequence} PEGA {name}".encode(), f"{sequence} NOK".encode())

        self.finish(15)

    def test_file_before_presentation(self):
        self.exchange(b"10 PEGA nonexistent.txt", b"10 NOK")
        self.assertEqual(self.connection.recv(1), b"")

    def test_list_after_error(self):
        self.authenticate()
        self.exchange(b"11 TRAP", b"11 NOK")
        self.connection.sendall(b"12 LIST")
        self.assertEqual(receive_field(self.connection), b"12")
        self.assertEqual(receive_field(self.connection), b"ARQS")
        count = int(receive_field(self.connection))
        directory = Path(__file__).resolve().parent / "files"
        names = sorted(path.name for path in directory.iterdir() if path.is_file())
        expected = ",".join(names).encode("ascii")
        self.assertEqual(count, len(names))
        self.assertEqual(receive_exactly(self.connection, len(expected)), expected)
        self.finish(13)

    def test_fragmented_request(self):
        for part in [b"10 CU", b"MP us", b"er1"]:
            self.connection.sendall(part)
            time.sleep(0.02)

        self.assertEqual(receive_exactly(self.connection, 5), b"10 OK")
        self.finish(11)

    def test_client_disconnects_without_term(self):
        self.authenticate()
        self.connection.close()

        with socket.create_connection((HOST, PORT), timeout=5) as connection:
            connection.sendall(b"100 CUMP user2")
            self.assertEqual(receive_exactly(connection, 6), b"100 OK")
            connection.sendall(b"101 TERM")
            self.assertEqual(receive_exactly(connection, 6), b"101 OK")
            self.assertEqual(connection.recv(1), b"")


if __name__ == "__main__":
    unittest.main(verbosity=2)
