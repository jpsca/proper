import socket


DISPLAY = """
   ┌─────────────────────────────────────────────────┐
   │   Running on:                                   │
   │   - Your machine:  {local}│
   │   - Your network:  {network}│
   │                                                 │
   │   Press `ctrl+c` to quit.                       │
   └─────────────────────────────────────────────────┘
"""


def on_start(host, port):
    local = "{:<29}".format(f"http://{host}:{port}")
    network = "{:<29}".format(f"http://{_get_local_ip()}:{port}")

    print(DISPLAY.format(local=local, network=network))


def _get_local_ip():
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


def on_exit(server):
    print("--- Goodbye! ---")
