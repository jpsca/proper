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
EXAMPLE_COM_IP = "93.184.216.34"


def welcome_message(host="0.0.0.0", port=2300):
    """Display the welcome message for the development server.

    Arguments:

    - host [0.0.0.0]
    - port [2300]

    """
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
        sock.connect((EXAMPLE_COM_IP, 1))
        ip = sock.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        sock.close()
    return ip
