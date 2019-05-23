#!/usr/bin/env python3
import socket
import time
import logging
import json
from threading import Thread

logger = logging.getLogger(__name__)


def path(_path):
    def wrapper(func):
        func._path = _path
        return func

    return wrapper


class WebServer(Thread):
    """
    Class for describing simple HTTP server
    """

    def __init__(self, host='localhost', port=8088):
        Thread.__init__(self)
        self.host = host
        self.port = port
        self._stopped = False
        self._handlers = dict()
        self.start()

    def register_handlers(self, obj):
        for methodname in dir(obj):
            method = getattr(obj, methodname)
            if hasattr(method, '_path'):
                self._handlers.update({method._path: method})

    def stop(self):
        """
        Shuts down the server
        """
        logger.debug("Shutting down server")
        self._stopped = True
        try:
            self.socket.shutdown(2)
        except OSError:
            pass
        self.socket.close()

    def _generate_headers(self, response_code):
        """
        Generate HTTP response headers.
        Parameters:
            - response_code: HTTP response code to add to the header. 200 and 404 supported
        Returns:
            A formatted HTTP header for the given response_code
        """
        header = ''
        if response_code == 200:
            header += 'HTTP/1.1 200 OK\n'
        elif response_code == 404:
            header += 'HTTP/1.1 404 Not Found\n'
        elif response_code == 406:
            header += 'HTTP/1.1 406 Not Acceptable\n'
        elif response_code == 500:
            header += 'HTTP/1.1 500 Internal Server Error\n'

        time_now = time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime())
        header += 'Date: {now}\n'.format(now=time_now)
        header += 'Server: r10kwebhook\n'
        header += 'Connection: close\n\n'  # Signal that connection will be closed after completing the request
        return header.encode()

    def run(self):
        """
        Attempts to create and bind a socket to launch the server. Listens on self.port for any incoming connections
        """

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            logger.info("Starting http-server on {host}:{port}".format(host=self.host, port=self.port))
            self.socket.bind((self.host, self.port))
            logger.debug("Server started on port {port}.".format(port=self.port))

        except Exception as e:
            logger.error("Could not bind to port {port}".format(port=self.port))
            self.stop()
            return

        self.socket.listen(3)
        while not self._stopped:
            try:
                client, address = self.socket.accept()
            except (ConnectionAbortedError, OSError):
                pass
            else:
                client.settimeout(3)
                logger.debug("Recieved connection from {addr}".format(addr=address))
                Thread(target=self._handle_client, args=(client, address)).start()

    def _handle_client(self, client, address):
        """
        Main loop for handling connecting clients and serving files from content_dir
        Parameters:
            - client: socket client from accept()
            - address: socket address from accept()
        """
        PACKET_SIZE = 1024
        logger.debug("CLIENT %s", client)
        data = packet = client.recv(PACKET_SIZE)  # Recieve data packet from client
        while len(packet) == PACKET_SIZE:
            packet = client.recv(PACKET_SIZE)  # Recieve data packet from client
            data += packet
        data = data.decode()

        if not data: return

        request_method = data.split(' ')[0]
        logger.debug("Method: {m}".format(m=request_method))
        logger.debug("Request Body: {b}".format(b=data))

        if request_method in ('GET', 'POST'):
            path = data.split(' ')[1]
            if path in self._handlers:
                data = data.split('\r\n\r\n')[1]
                if data:
                    try:
                        data = json.loads(data)
                    except Exception as err:
                        logger.exception(err)
                        client.send(self._generate_headers(406))
                        client.close()
                        return
                try:
                    response_data = self._handlers[path](data).encode()
                except Exception as err:
                    logger.exception(err)
                    response = self._generate_headers(500)
                else:
                    response = self._generate_headers(200) + response_data
            else:
                response = self._generate_headers(404) + 'not found'.encode()
            client.send(response)
            client.close()
            return
        else:
            logger.debug("Unknown HTTP request method: {method}".format(method=request_method))
