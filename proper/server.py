from datetime import datetime
import logging
import sys

from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler


logger = logging.getLogger()


DISPLAY = """
   ┌─────────────────────────────────────────────────┐
   │   Running on:                                   │
   │   - Your machine:  {local}│
   │   - Your network:  {network}│
   │                                                 │
   │   Press `ctrl+c` to quit.                       │
   └─────────────────────────────────────────────────┘
"""


def display_running_message(host, port):  # pragma: no cover
    import socket

    local = "{:<29}".format(f"http://{host}:{port}")
    local_ip = socket.gethostbyname(socket.gethostname())
    network = "{:<29}".format(f"http://{local_ip}:{port}")

    print(DISPLAY.format(local=local, network=network))


def add_time_unit(delta):
    if delta >= 0.01:
        return str(int(delta * 1000)) + "ms"
    if delta >= 0.0001:
        return str(int(delta * 10000)) + "μs"
    return str(int(delta * 100000)) + "ns"


def add_size_unit(size):
    if size < 1000:
        return str(size) + "B"
    if size < 10000:
        return str(int(size / 100) / 10) + "KB"
    return str(int(size / 1000) / 10) + "MB"


class ProperWebSocketHandler(WebSocketHandler):

    # prevent the WebSocketHandler to call the underlying WSGI application,
    # but only setup the WebSocket negotiations
    prevent_wsgi_call = True

    def format_request(self):
        if isinstance(self.client_address, tuple):
            client_address = self.client_address[0]
        else:
            client_address = self.client_address

        if self.response_length:
            length = add_size_unit(self.response_length)
        else:
            length = "-"

        if self.time_finish:
            delta = add_time_unit(self.time_finish - self.time_start)
        else:
            delta = "-"

        now = datetime.now()

        return "{} {} -> {} {} {} {}".format(
            now.strftime("%H:%M:%S"),
            client_address or "?",
            (self.requestline or "").rsplit(" ", 1)[0],
            self._orig_status.split()[0],
            length,
            delta,
        )


def set_logger(app):
    level = logging.INFO if app.debug else logging.ERROR
    logger.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    formatter = logging.Formatter("%(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def run_server(app, host, port):
    set_logger(app)
    server = pywsgi.WSGIServer(
        (host, port), app.wsgi, handler_class=ProperWebSocketHandler
    )
    return server.serve_forever()
