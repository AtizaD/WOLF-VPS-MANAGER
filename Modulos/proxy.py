#!/usr/bin/env python3
# encoding: utf-8
import socket
import threading
import select
import signal
import sys
import time
import logging
import argparse
from typing import List, Tuple, Optional
from dataclasses import dataclass

@dataclass
class ProxyConfig:
    host: str = '0.0.0.0'
    port: int = 80
    buffer_size: int = 8196 * 8
    timeout: int = 60
    password: str = ''
    default_host: str = '0.0.0.0:22'
    status_message: str = ''
    status_color: str = 'null'
    max_connections: int = 1000
    connection_timeout: int = 300

    def __post_init__(self):
        self.response = f"HTTP/1.1 200 <font color=\"{self.status_color}\">{self.status_message}</font>\r\n\r\n"

class ConnectionHandler(threading.Thread):
    def __init__(self, client: socket.socket, server: 'Server', addr: Tuple[str, int], config: ProxyConfig):
        super().__init__()
        self.client = client
        self.client_buffer = ''
        self.server = server
        self.config = config
        self.target: Optional[socket.socket] = None
        self.client_closed = False
        self.target_closed = True
        self.addr = addr
        self.logger = logging.getLogger('proxy.connection')
        self.last_activity = time.time()

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
                elif host_port.startswith(self.config.host):
                    self.handle_connect(host_port)
                else:
                    self.client.send(b'HTTP/1.1 403 Forbidden!\r\n\r\n')
            else:
                self.logger.warning(f'No X-Real-Host from {self.addr[0]}')
                self.client.send(b'HTTP/1.1 400 NoXRealHost!\r\n\r\n')

        except Exception as e:
            self.logger.error(f"Connection error from {self.addr[0]}: {str(e)}")
        finally:
            self.close()
            self.server.remove_conn(self)

    def find_header(self, head: str, header: str) -> str:
        try:
            aux = head.find(f'{header}: ')
            if aux == -1:
                return ''
            
            aux = head.find(':', aux)
            head = head[aux + 2:]
            aux = head.find('\r\n')
            
            if aux == -1:
                return ''
                
            return head[:aux]
        except Exception as e:
            self.logger.error(f"Header parsing error: {str(e)}")
            return ''

    def connect_target(self, host: str) -> None:
        try:
            i = host.find(':')
            if i != -1:
                port = int(host[i + 1:])
                host = host[:i]
            else:
                port = 22

            address_info = socket.getaddrinfo(host, port)[0]
            self.target = socket.socket(address_info[0], address_info[1])
            self.target.settimeout(self.config.connection_timeout)
            self.target_closed = False
            self.target.connect(address_info[4])
            
        except Exception as e:
            self.logger.error(f"Failed to connect to target {host}:{port} - {str(e)}")
            raise

    def handle_connect(self, path: str) -> None:
        try:
            self.connect_target(path)
            self.client.sendall(self.config.response.encode())
            self.client_buffer = ''
            self.tunnel()
        except Exception as e:
            self.logger.error(f"Connection handling error: {str(e)}")
            self.close()

    def tunnel(self) -> None:
        sockets = [self.client, self.target]
        timeout = 0
        while True:
            try:
                self.last_activity = time.time()
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

                # Check for connection timeout
                if time.time() - self.last_activity > self.config.connection_timeout:
                    self.logger.debug(f"Connection timeout from {self.addr[0]}")
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
            self.socket.bind((self.config.host, self.config.port))
            self.socket.listen(self.config.max_connections)
            self.running = True
            
            while self.running:
                try:
                    client, addr = self.socket.accept()
                    if len(self.threads) >= self.config.max_connections:
                        self.logger.warning(f"Maximum connections reached, rejecting {addr[0]}")
                        client.close()
                        continue
                        
                    client.settimeout(self.config.connection_timeout)
                    conn = ConnectionHandler(client, self, addr, self.config)
                    conn.start()
                    self.add_conn(conn)
                    self.logger.info(f"New connection from {addr[0]}")
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
                self.logger.debug(f"Active connections: {len(self.threads)}")

    def remove_conn(self, conn: ConnectionHandler) -> None:
        with self.lock:
            try:
                self.threads.remove(conn)
                self.logger.debug(f"Active connections: {len(self.threads)}")
            except ValueError:
                pass

    def close(self) -> None:
        self.running = False
        with self.lock:
            for conn in self.threads[:]:
                conn.close()
        if self.socket:
            self.socket.close()

def setup_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('/var/log/socksproxy.log')
        ]
    )

def print_banner(config: ProxyConfig) -> None:
    banner = f"""
\033[0;34m{'━' * 8}\033[1;32m PROXY SOCKS\033[0;34m{'━' * 8}
\033[1;33mIP:\033[1;32m {config.host}
\033[1;33mPORT:\033[1;32m {config.port}
\033[0;34m{'━' * 10}\033[1;32m VPSMANAGER\033[0;34m{'━'}\033[1;37m{'━' * 11}
"""
    print(banner)

def parse_args() -> ProxyConfig:
    parser = argparse.ArgumentParser(description='Advanced SOCKS Proxy Server')
    parser.add_argument('-p', '--port', type=int, default=80, help='Port to listen on')
    parser.add_argument('-b', '--bind', default='0.0.0.0', help='Address to bind to')
    parser.add_argument('--max-connections', type=int, default=1000, help='Maximum concurrent connections')
    parser.add_argument('--timeout', type=int, default=300, help='Connection timeout in seconds')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    return ProxyConfig(
        host=args.bind,
        port=args.port,
        max_connections=args.max_connections,
        connection_timeout=args.timeout
    )

def main() -> None:
    config = parse_args()
    setup_logging(True)
    print_banner(config)
    
    server = Server(config)
    server.start()

    def signal_handler(signum, frame):
        print('\nShutting down gracefully...')
        server.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        while True:
            time.sleep(1)
            # Monitor and report status periodically
            if server.running:
                with server.lock:
                    active_conns = len(server.threads)
                if active_conns > 0:
                    logging.info(f"Active connections: {active_conns}")
    except KeyboardInterrupt:
        print('\nShutting down gracefully...')
        server.close()

if __name__ == '__main__':
    main()
