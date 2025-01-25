#!/usr/bin/env python3
# encoding: utf-8

import socket
import threading
import select
import logging
import argparse
import os
import time
import signal

# Default configuration
DEFAULT_HOST = os.getenv("DEFAULT_HOST", "127.0.0.1:22")
BUFLEN = 8196 * 8
TIMEOUT = 60
PASS = os.getenv("PROXY_PASS", "")  # Password can be set using an environment variable

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ProxyServer")


class Server(threading.Thread):
    def __init__(self, host: str, port: int):
        super().__init__()
        self.host = host
        self.port = port
        self.running = False
        self.threads = []
        self.lock = threading.Lock()

    def run(self):
        """Run the server and handle incoming connections."""
        self.running = True
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(5)
            logger.info(f"Server started on {self.host}:{self.port}")

            while self.running:
                try:
                    client_socket, addr = self.socket.accept()
                    client_socket.setblocking(1)
                    conn_handler = ConnectionHandler(client_socket, self, addr)
                    conn_handler.start()
                    self.add_thread(conn_handler)
                except socket.timeout:
                    continue
                except Exception as e:
                    logger.error(f"Error accepting connection: {e}")

        except Exception as e:
            logger.error(f"Server error: {e}")
        finally:
            self.shutdown()

    def add_thread(self, thread):
        """Add a thread to the server."""
        with self.lock:
            if self.running:
                self.threads.append(thread)

    def remove_thread(self, thread):
        """Remove a thread from the server."""
        with self.lock:
            if thread in self.threads:
                self.threads.remove(thread)

    def shutdown(self):
        """Stop the server and cleanup."""
        self.running = False
        with self.lock:
            for thread in self.threads:
                thread.close()
                thread.join()
        if hasattr(self, "socket"):
            self.socket.close()
        logger.info("Server stopped")


class ConnectionHandler(threading.Thread):
    def __init__(self, client_socket, server, addr):
        super().__init__()
        self.client_socket = client_socket
        self.server = server
        self.addr = addr
        self.target_socket = None

    def close(self):
        """Close client and target sockets."""
        try:
            if self.client_socket:
                self.client_socket.shutdown(socket.SHUT_RDWR)
                self.client_socket.close()
        except Exception:
            pass

        try:
            if self.target_socket:
                self.target_socket.shutdown(socket.SHUT_RDWR)
                self.target_socket.close()
        except Exception:
            pass

    def run(self):
        """Handle the connection."""
        try:
            client_buffer = self.client_socket.recv(BUFLEN)
            host_port = self.get_header(client_buffer, "X-Real-Host") or DEFAULT_HOST
            password = self.get_header(client_buffer, "X-Pass")

            if PASS and password != PASS:
                self.client_socket.sendall(b"HTTP/1.1 403 Forbidden\r\n\r\n")
                logger.warning(f"Authentication failed from {self.addr}")
                return

            logger.info(f"{self.addr} connecting to {host_port}")
            self.connect_target(host_port)
            self.client_socket.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            self.forward_traffic()

        except Exception as e:
            logger.error(f"Error handling connection from {self.addr}: {e}")
        finally:
            self.close()
            self.server.remove_thread(self)

    def connect_target(self, host_port: str):
        """Connect to the target server."""
        try:
            host, port = host_port.split(":")
            port = int(port)
            self.target_socket = socket.create_connection((host, port))
        except Exception as e:
            logger.error(f"Failed to connect to {host_port}: {e}")
            raise

    def forward_traffic(self):
        """Forward data between the client and the target server."""
        sockets = [self.client_socket, self.target_socket]
        while True:
            try:
                readable, _, _ = select.select(sockets, [], sockets, TIMEOUT)
                for sock in readable:
                    data = sock.recv(BUFLEN)
                    if not data:
                        return
                    if sock is self.client_socket:
                        self.target_socket.sendall(data)
                    else:
                        self.client_socket.sendall(data)
            except Exception as e:
                logger.error(f"Traffic forwarding error: {e}")
                break

    def get_header(self, buffer: bytes, header_name: str) -> str:
        """Extract a header value from the buffer."""
        try:
            headers = buffer.decode("utf-8").split("\r\n")
            for header in headers:
                if header.lower().startswith(header_name.lower() + ":"):
                    return header.split(":", 1)[1].strip()
        except Exception as e:
            logger.error(f"Header parsing error: {e}")
        return ""


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Simple SOCKS/HTTP Proxy Server")
    parser.add_argument("-b", "--bind", default="0.0.0.0", help="IP address to bind the server")
    parser.add_argument("-p", "--port", type=int, default=80, help="Port to bind the server")
    return parser.parse_args()


def main():
    args = parse_arguments()
    server = Server(args.bind, args.port)

    # Graceful shutdown on Ctrl+C
    def signal_handler(sig, frame):
        logger.info("Stopping server...")
        server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    server.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(None, None)


if __name__ == "__main__":
    main()
