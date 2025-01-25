#!/usr/bin/env python3
# encoding: utf-8

import os
import socket
import threading
import select
import signal
import sys
import time
import getopt
sudo update-alternatives --install /usr/bin/python python /usr/bin/python3 1


# Configuration
PASS = ''
LISTENING_ADDR = '0.0.0.0'
DEFAULT_HOST = "127.0.0.1:22"
BUFLEN = 4096 * 4
TIMEOUT = 60
RESPONSE = "HTTP/1.1 101 Switching Protocols\r\n\r\n"


class Server(threading.Thread):
    def __init__(self, host, port):
        super().__init__()
        self.running = False
        self.host = host
        self.port = port
        self.threads = []
        self.threadsLock = threading.Lock()
        self.logLock = threading.Lock()

    def run(self):
        self.soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.soc.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.soc.bind((self.host, self.port))
        self.soc.listen(5)
        self.running = True
        print(f"Server running on {self.host}:{self.port}")

        try:
            while self.running:
                try:
                    client_socket, addr = self.soc.accept()
                    client_socket.setblocking(1)
                except socket.timeout:
                    continue

                conn = ConnectionHandler(client_socket, self, addr)
                conn.start()
                self.addConn(conn)
        except Exception as e:
            print(f"Server error: {e}")
        finally:
            self.close()

    def log(self, message):
        with self.logLock:
            print(message)

    def addConn(self, conn):
        with self.threadsLock:
            if self.running:
                self.threads.append(conn)

    def removeConn(self, conn):
        with self.threadsLock:
            if conn in self.threads:
                self.threads.remove(conn)

    def close(self):
        self.running = False
        with self.threadsLock:
            for conn in self.threads:
                conn.close()
        self.soc.close()
        print("Server stopped")


class ConnectionHandler(threading.Thread):
    def __init__(self, client_socket, server, addr):
        super().__init__()
        self.client = client_socket
        self.server = server
        self.addr = addr
        self.target = None
        self.client_buffer = b''

    def close(self):
        try:
            if self.client:
                self.client.close()
        except:
            pass

        try:
            if self.target:
                self.target.close()
        except:
            pass

    def findHeader(self, buffer, header):
        try:
            buffer_str = buffer.decode('utf-8')
            for line in buffer_str.split("\r\n"):
                if line.lower().startswith(header.lower() + ":"):
                    return line.split(":", 1)[1].strip()
        except Exception as e:
            self.server.log(f"Header parsing error: {e}")
        return ""

    def connect_target(self, host):
        try:
            host, port = host.split(':')
            port = int(port)
        except ValueError:
            host = host
            port = 443 if self.method == 'CONNECT' else 80

        self.target = socket.create_connection((host, port))

    def method_CONNECT(self, path):
        self.server.log(f"{self.addr} - CONNECT {path}")
        try:
            self.connect_target(path)
            self.client.sendall(RESPONSE.encode('utf-8'))
            self.forward_data()
        except Exception as e:
            self.server.log(f"Connection error: {e}")

    def forward_data(self):
        sockets = [self.client, self.target]
        while True:
            try:
                readable, _, _ = select.select(sockets, [], sockets, 3)
                for sock in readable:
                    data = sock.recv(BUFLEN)
                    if not data:
                        return

                    if sock is self.client:
                        self.target.sendall(data)
                    else:
                        self.client.sendall(data)
            except Exception as e:
                self.server.log(f"Data forwarding error: {e}")
                break

    def run(self):
        try:
            self.client_buffer = self.client.recv(BUFLEN)
            host_port = self.findHeader(self.client_buffer, 'X-Real-Host') or DEFAULT_HOST
            passwd = self.findHeader(self.client_buffer, 'X-Pass')

            if PASS and passwd != PASS:
                self.client.sendall(b'HTTP/1.1 403 Forbidden\r\n\r\n')
            else:
                self.method_CONNECT(host_port)
        except Exception as e:
            self.server.log(f"{self.addr} - Error: {e}")
        finally:
            self.close()


def parse_args(argv):
    global LISTENING_ADDR
    global LISTENING_PORT

    LISTENING_PORT = 80  # Default port

    try:
        opts, args = getopt.getopt(argv, "hb:p:", ["bind=", "port="])
    except getopt.GetoptError:
        print("Usage: proxy.py -b <bind_address> -p <port>")
        sys.exit(2)

    for opt, arg in opts:
        if opt in ("-b", "--bind"):
            LISTENING_ADDR = arg
        elif opt in ("-p", "--port"):
            LISTENING_PORT = int(arg)


def main():
    parse_args(sys.argv[1:])
    print("\033[0;34m━" * 8, "\033[1;32m PROXY WEBSOCKET ", "\033[0;34m━" * 8, "\n")
    print(f"\033[1;33mIP:\033[1;32m {LISTENING_ADDR}")
    print(f"\033[1;33mPORT:\033[1;32m {LISTENING_PORT}\n")

    server = Server(LISTENING_ADDR, LISTENING_PORT)
    server.start()

    try:
        while True:
            time.sleep(2)
    except KeyboardInterrupt:
        print("Stopping server...")
        server.close()


if __name__ == "__main__":
    main()
