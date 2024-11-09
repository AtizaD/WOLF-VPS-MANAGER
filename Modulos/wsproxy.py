#!/usr/bin/env python3
# encoding: utf-8
import socket
import threading
import select
import signal
import sys
import time
import getopt
import logging
from typing import List, Tuple, Optional
from dataclasses import dataclass

@dataclass
class ProxyConfig:
    listen_addr: str = '0.0.0.0'
    listen_port: int = 80
    buffer_size: int = 4096 * 4
    timeout: int = 60
    password: str = ''
    default_host: str = '127.0.0.1:22'
    status_message: str = ''
    status_color: str = 'null'

    def __post_init__(self):
        self.response = f"HTTP/1.1 101 <font color=\"{self.status_color}\">{self.status_message}</font>\r\n\r\n"

class ConnectionHandler(threading.Thread):
    def __init__(self, client_socket: socket.socket, server: 'Server', addr: Tuple[str, int], config: ProxyConfig):
        super().__init__()
        self.client = client_socket
        self.client_buffer = ''
        self.server = server
        self.config = config
        self.target: Optional[socket.socket] = None
        self.client_closed = False
        self.target_closed = True
        self.log = f'Connection from: {addr}'
        self.logger = logging.getLogger('proxy.connection')

    def close(self) -> None:
        try:
            if not self.client_closed:
                self.client.shutdown(socket.SHUT_RDWR)
                self.client.close()
        except Exception as e:
            self.logger.debug(f"Error closing client: {e}")
        finally:
            self.client_closed = True

        try:
            if not self.target_closed and self.target:
                self.target.shutdown(socket.SHUT_RDWR)
                self.target.close()
        except Exception as e:
            self.logger.debug(f"Error closing target: {e}")
        finally:
            self.target_closed = True

    def run(self) -> None:
        try:
            self.client_buffer = self.client.recv(self.config.buffer_size).decode()
            host_port = self.find_header(self.client_buffer, 'X-Real-Host')
            
            if not host_port:
                host_port = self.config.default_host

            split = self.find_header(self.client_buffer, 'X-Split')
            if split:
                self.client.recv(self.config.buffer_size)

            if host_port:
                password = self.find_header(self.client_buffer, 'X-Pass')
                
                if self.config.password and password == self.config.password:
                    self.handle_connect(host_port)
                elif self.config.password and password != self.config.password:
                    self.client.send(b'HTTP/1.1 400 WrongPass!\r\n\r\n')
                elif host_port.startswith(('127.0.0.1', 'localhost')):
                    self.handle_connect(host_port)
                else:
                    self.client.send(b'HTTP/1.1 403 Forbidden!\r\n\r\n')
            else:
                self.logger.warning('No X-Real-Host header found')
                self.client.send(b'HTTP/1.1 400 NoXRealHost!\r\n\r\n')

        except Exception as e:
            self.logger.error(f"Connection error: {str(e)}")
        finally:
            self.close()
            self.server.remove_conn(self)

    def find_header(self, head: str, header: str) -> str:
        aux = head.find(f'{header}: ')
        if aux == -1:
            return ''
        
        aux = head.find(':', aux)
        head = head[aux + 2:]
        aux = head.find('\r\n')
        
        if aux == -1:
            return ''
            
        return head[:aux]

    def connect_target(self, host: str) -> None:
        i = host.find(':')
        if i != -1:
            port = int(host[i + 1:])
            host = host[:i]
        else:
            port = 443 if hasattr(self, 'method') and self.method == 'CONNECT' else 80

        try:
            address_info = socket.getaddrinfo(host, port)[0]
            self.target = socket.socket(address_info[0], address_info[1])
            self.target_closed = False
            self.target.connect(address_info[4])
        except Exception as e:
            self.logger.error(f"Failed to connect to target {host}:{port} - {str(e)}")
            raise

    def handle_connect(self, path: str) -> None:
        self.log += f' - CONNECT {path}'
        self.connect_target(path)
        self.client.sendall(self.config.response.encode())
        self.client_buffer = ''
        self.server.log_message(self.log)
        self.tunnel()

    def tunnel(self) -> None:
        sockets = [self.client, self.target]
        timeout = 0
        while True:
            try:
                recv, _, err = select.select(sockets, [], sockets, 3)
                if err:
                    break

                if recv:
                    for in_sock in recv:
                        try:
                            data = in_sock.recv(self.config.buffer_size)
                            if not data:
                                break

                            if in_sock is self.target:
                                self.client.send(data)
                            else:
                                self.target.send(data)
                            timeout = 0
                        except Exception as e:
                            self.logger.debug(f"Tunnel error: {str(e)}")
                            break

                timeout += 1
                if timeout == self.config.timeout:
                    break
            except Exception as e:
                self.logger.debug(f"Tunnel select error: {str(e)}")
                break

class Server(threading.Thread):
    def __init__(self, config: ProxyConfig):
        super().__init__()
        self.config = config
        self.running = False
        self.socket: Optional[socket.socket] = None
        self.threads: List[ConnectionHandler] = []
        self.lock = threading.Lock()
        self.logger = logging.getLogger('proxy.server')

    def run(self) -> None:
        self.socket = socket.socket(socket.AF_INET)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.settimeout(2)

        try:
            self.socket.bind((self.config.listen_addr, self.config.listen_port))
            self.socket.listen(0)
            self.running = True
            
            while self.running:
                try:
                    client, addr = self.socket.accept()
                    client.setblocking(True)
                    conn = ConnectionHandler(client, self, addr, self.config)
                    conn.start()
                    self.add_conn(conn)
                except socket.timeout:
                    continue
                except Exception as e:
                    self.logger.error(f"Accept error: {str(e)}")
                    if not self.running:
                        break
        finally:
            self.running = False
            if self.socket:
                self.socket.close()

    def add_conn(self, conn: ConnectionHandler) -> None:
        with self.lock:
            if self.running:
                self.threads.append(conn)

    def remove_conn(self, conn: ConnectionHandler) -> None:
        with self.lock:
            try:
                self.threads.remove(conn)
            except ValueError:
                pass

    def close(self) -> None:
        self.running = False
        with self.lock:
            for conn in self.threads[:]:
                conn.close()
        if self.socket:
            self.socket.close()

    def log_message(self, message: str) -> None:
        self.logger.info(message)

def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('/var/log/proxy.log')
        ]
    )

def print_banner(config: ProxyConfig) -> None:
    banner = f"""
{'━' * 8} PROXY WEBSOCKET {'━' * 8}
IP: {config.listen_addr}
PORT: {config.listen_port}
{'━' * 10} ◇────────────ㅤ🐉ㅤWOLF VPS MANAGERㅤ🐉ㅤ────────────◇ {'━' * 11}
"""
    print(banner)

def parse_args(argv: List[str]) -> ProxyConfig:
    config = ProxyConfig()
    
    try:
        opts, _ = getopt.getopt(argv, "hb:p:", ["bind=", "port="])
        for opt, arg in opts:
            if opt == '-h':
                print('Usage: proxy.py -p <port>')
                print('       proxy.py -b <ip> -p <port>')
                print('       proxy.py -b 0.0.0.0 -p 22')
                sys.exit()
            elif opt in ("-b", "--bind"):
                config.listen_addr = arg
            elif opt in ("-p", "--port"):
                config.listen_port = int(arg)
    except getopt.GetoptError:
        print('Invalid arguments')
        sys.exit(2)
    except ValueError:
        print('Port must be a number')
        sys.exit(2)
        
    return config

def main() -> None:
    config = parse_args(sys.argv[1:])
    setup_logging()
    print_banner(config)
    
    server = Server(config)
    server.start()

    def signal_handler(signum, frame):
        print('\nShutting down...')
        server.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print('\nShutting down...')
        server.close()

if __name__ == '__main__':
    main()
