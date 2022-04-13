from typing import Tuple


def parse_host(host: str, default_port: int) -> Tuple[str, int]:
    if not host:
        return "", default_port

    sport = ""
    if "]:" in host:
        host, sport = host.split("]:", 1)
        host = host[1:]
    elif host[0] == "[":
        host = host[1:-1]
    elif ":" in host:
        host, sport = host.rsplit(":", 1)

    port = int(sport) if sport and sport.isdecimal() else default_port
    return host, port
