"""How Proper scales across threads in one process, without a server.

    python -m benchmarks.threads [/plaintext] [--threads 1,2,4,8,16] [--requests 20000]

Calls the app as a WSGI callable from N threads at once and prints requests
per second and the efficiency against N times the single-thread rate. On
free-threaded Python this shows contention inside the interpreter and the
framework; on the GIL build it shows the GIL.
"""
import argparse
import io
import sys
import threading
import time

from benchmarks.app import make_app


def make_environ(path: str) -> dict:
    return {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "SERVER_NAME": "127.0.0.1",
        "SERVER_PORT": "8123",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "REMOTE_ADDR": "127.0.0.1",
        "REMOTE_PORT": "5555",
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(b""),
        "HTTP_HOST": "127.0.0.1:8123",
        "HTTP_USER_AGENT": "bombardier",
        "HTTP_ACCEPT": "*/*",
    }


def run(app, path: str, threads: int, requests: int) -> float:
    def worker():
        environ = make_environ(path)
        sent = {}

        def start_response(status, headers):
            sent["status"] = status

        for _ in range(requests):
            environ["wsgi.input"].seek(0)
            body = app(environ, start_response)
            assert sent["status"].startswith("200"), sent["status"]
            close = getattr(body, "close", None)
            if close:
                close()

    pool = [threading.Thread(target=worker) for _ in range(threads)]
    started = time.perf_counter()
    for th in pool:
        th.start()
    for th in pool:
        th.join()
    return threads * requests / (time.perf_counter() - started)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default="/plaintext")
    ap.add_argument("--threads", default="1,2,4,8,16")
    ap.add_argument("--requests", type=int, default=20000)
    args = ap.parse_args()

    app = make_app()
    run(app, args.path, 1, 500)  # warm up
    gil = getattr(sys, "_is_gil_enabled", lambda: True)()
    print(f"{args.path}, GIL {'on' if gil else 'off'}")
    base = None
    for n in (int(x) for x in args.threads.split(",")):
        rps = run(app, args.path, n, args.requests // n)
        base = base or rps
        print(f"{n:3} threads: {rps:>10,.0f} req/s   {rps / (base * n):5.0%} of linear")


if __name__ == "__main__":
    main()
