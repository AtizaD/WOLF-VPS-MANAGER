import socket
import threading
import select
import configparser  # Added for configuration file

# Read configuration from a file (modify path as needed)
config = configparser.ConfigParser()
config.read('proxy.conf')

# Load configuration from file
LISTENING_ADDR = config['DEFAULT'].get('listening_addr', '0.0.0.0')
LISTENING_PORT = config['DEFAULT'].getint('listening_port', 80)
PASSWORD = config['DEFAULT'].get('password')  # Optional password
TIMEOUT = config['DEFAULT'].getint('timeout', 60)
BUFLEN = config['DEFAULT'].getint('buffer_size', 4096 * 4)

DEFAULT_HOST = "127.0.0.1:22"
RESPONSE = "HTTP/1.1 101 OK\r\n\r\n"


class Server(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.running = False
        self.threads = []
        self.lock = threading.Lock()

    def run(self):
        self.soc = socket.socket(socket.AF_INET)
        self.soc.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.soc.settimeout(2)
        self.soc.bind((LISTENING_ADDR, LISTENING_PORT))
        self.soc.listen(0)
        self.running = True

        try:
            while self.running:
                try:
                    c, addr = self.soc.accept()
                    c.setblocking(1)
                    conn = ConnectionHandler(c, self, addr)
                    conn.start()
                    self.add_conn(conn)
                except socket.timeout:
                    pass
        finally:
            self.running = False
            self.soc.close()

    def add_conn(self, conn):
        with self.lock:
            self.threads.append(conn)

    def remove_conn(self, conn):
        with self.lock:
            self.threads.remove(conn)

    def close(self):
        self.running = False
        with self.lock:
            threads = list(self.threads)
            for c in threads:
                c.close()


class ConnectionHandler(threading.Thread):
    def __init__(self, socClient, server, addr):
        threading.Thread.__init__(self)
        self.client_closed = False
        self.target_closed = True
        self.client = socClient
        self.client_buffer = ''
        self.server = server
        self.log = 'Connection: ' + str(addr)

    def close(self):
        try:
            if not self.client_closed:
                self.client.shutdown(socket.SHUT_RDWR)
                self.client.close()
        except:
            pass
        finally:
            self.client_closed = True

        try:
            if not self.target_closed:
                self.target.shutdown(socket.SHUT_RDWR)
                self.target.close()
        except:
            pass
        finally:
            self.target_closed = True

    def run(self):
        try:
            self.client_buffer = self.client.recv(BUFLEN)

            host_port = self.find_header(self.client_buffer, 'X-Real-Host')
            if host_port == '':
                host_port = DEFAULT_HOST

            split = self.find_header(self.client_buffer, 'X-Split')

            if host_port != '':
                # Implement user authentication here (if PASSWORD is set)
                if PASSWORD and self.authenticate(self.find_header(self.client_buffer, 'X-Pass')) != PASSWORD:
                    self.client.send('HTTP/1.1 401 Unauthorized\r\n\r\n')
                    return
                elif host_port.startswith('127.0.0.1') or host_port.startswith('localhost'):
                    self.method_CONNECT(host_port)
                else:
			self.client.send('HTTP/1.1 403 Forbidden!\r\n\r\n')
        except Exception as e:
            self.log += ' - error: ' + str(e)
            self.server.log(self.log)
        finally:
            self.close()
            self.server.remove_conn(self)

    def find_header(self, head, header):
        aux = head.find(header + ': ')
        if aux == -1:
            return ''
        aux = head.find(':', aux)
        head = head[aux + 2:]
        aux = head.find('\r\n')
        if aux == -1:
            return ''
        return head[:aux]

    def connect_target(self, host):
        i = host.find(':')
        if i != -1:
            port = int(host[i + 1:])
            host = host[:i]
        else:
            if self.method == 'CONNECT':
                port = 443
            else:
                port = 80

        (soc_family, soc_type, proto, _, address) = socket.getaddrinfo(host, port)[0]

        self.target = socket.socket(soc_family, soc_type, proto)
        self.target_closed = False
        self.target.connect(address)

    def method_CONNECT(self, path):
        self.log += ' - CONNECT ' + path

        self.connect_target(path)
        self.client.sendall(RESPONSE)
        self.client_buffer = ''

        self.server.log(self.log)
        self.do_connect()

    def do_connect(self):
        socs = [self.client, self.target]
        while True:
            try:
                recv, _, err = select.select(socs, [], socs, TIMEOUT)
                if err:
                    # Handle errors
                    break
                if recv:
                    for in_ in recv:
                        try:
                            data = in_.recv(BUFLEN)
                            if data:
                                if in_ is self.target:
                                    self.client.send(data)
                                else:
                                    while data:
                                        byte = self.target.send(data)
                                        data = data[byte:]
                        except:
                            # Handle errors
                            break
            except select.error:
                # Handle timeout errors
                break

    def authenticate(self, password):
        # Implement your authentication logic here (e.g., check password against a database)
        # This is a placeholder, replace with your actual authentication mechanism
        return password == PASSWORD  # Replace with your logic

def main():
    server = Server()
    server.start()

    while True:
        try:
            time.sleep(2)
        except KeyboardInterrupt:
            print('stopping...')
            server.close()
            break

if __name__ == '__main__':
    main()

