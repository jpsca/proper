import socket


BANNER = """
░███████████
 ░███    ░███
 ░███    ░███░████████ ░██████ ░████████    ░██████ ░████████
 ░██████████  ░███ ░██░███ ░███ ░███  ░███ ░███ ░███ ░███ ░██
 ░███         ░███    ░███ ░███ ░███  ░███ ░███████  ░███
 ░███         ░███    ░███ ░███ ░███  ░███ ░███      ░███
░█████       ░█████    ░██████  ░███████    ░██████ ░█████
                                ░███
                                ░███
                               ░█████
"""

WELCOME = """
 ┌──────────────────────────{border}┐
 │                          {space}│
 │   Running on:            {space}│
 │   - Your machine:  {local}   │
 │   - Your network:  {network}   │
 │                          {space}│
 │   Press `ctrl+c` to quit.{space}│
 │                          {space}│
 └──────────────────────────{border}┘
"""

EXAMPLE_COM_IP = "93.184.216.34"


def show_banner() -> None:
    print(BANNER)


def show_welcome(host: str = "0.0.0.0", port: str | int = 2300) -> None:
    """Display the welcome message for the development server.

    Arguments:

    - host [0.0.0.0]

    - port [2300]

    """
    local_value = f"http://{host}:{port}"
    network_value = f"http://{_get_local_ip()}:{port}"
    size = max(len(local_value), len(network_value))

    local = f"{local_value}{' ' * (size - len(local_value))}"
    network = f"{network_value}{' ' * (size - len(network_value))}"
    border = "─" * (size - 3)
    space = " " * (size - 3)

    print(WELCOME.format(local=local, network=network, border=border, space=space))



def _get_local_ip() -> str:
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
