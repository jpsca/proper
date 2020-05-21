from datetime import datetime
import logging
import socket
import sys

from gevent import pywsgi


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


class ProperWSGIHandler(pywsgi.WSGIHandler):

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
    server = pywsgi.WSGIServer((host, port), app.wsgi, handler_class=ProperWSGIHandler)
    return server.serve_forever()
