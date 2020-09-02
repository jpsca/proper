import logging
import socket
import sys
from datetime import datetime

import hupper
from gevent.pywsgi import WSGIServer
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


class AppServer:
    sio = None

    def _set_logger(self):
        level = logging.INFO if self.config.debug else logging.ERROR
        logger.setLevel(level)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter("%(levelname)s %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    def run_with_reloader(self):
        reloader = hupper.start_reloader("wsgi.run")
        reloader.watch_files(self.config.server.watch)

    def run(self):
        self._set_logger()
        display_running_message(self.config.host, self.config.port)
        try:
            server = WSGIServer(
                (self.config.host, self.config.port),
                self,
                handler_class=ProperWSGIHandler,
            )
            server.serve_forever()
        except KeyboardInterrupt:
            print("Goodbye!\n")


def display_running_message(host, port):  # pragma: no cover
    local = "{:<29}".format(f"http://{host}:{port}")
    network = "{:<29}".format(f"http://{get_local_ip()}:{port}")

    print(DISPLAY.format(local=local, network=network))


def get_local_ip():
    ip = socket.gethostbyname(socket.gethostname())
    if not ip.startswith("127."):
        return ip
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        sock.connect(("8.8.8.8", 1))
        ip = sock.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        sock.close()
    return ip


class ProperWSGIHandler(WebSocketHandler):
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


def add_time_unit(delta):
    if delta >= 0.001:
        return str(int(delta * 1000)) + "ms"
    if delta >= 0.000001:
        return str(int(delta * 1000000)) + "μs"
    return str(int(delta * 1000000000)) + "ns"


def add_size_unit(size):
    if size < 1000:
        return str(size) + "B"
    if size < 10000:
        return str(int(size / 100) / 10) + "KB"
    return str(int(size / 1000) / 10) + "MB"
