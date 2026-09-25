"""RSGI entrypoint for Granian: `granian --interface rsgi benchmarks.rsgi:app`.

This is a thin shim: it rebuilds an ASGI-shaped scope from the RSGI scope
and calls the app's existing HTTP path. It measures the server swap only,
so it is a LOWER BOUND of what a native RSGI `Request` would give: the
headers still get re-parsed in Python here.
"""
import asyncio

from proper import current
from .app import make_app


proper_app = make_app()


class RsgiApp:
    def __init__(self, app):
        self.app = app

    def __rsgi_init__(self, loop):
        async def start():
            # `_setup_executor` needs a running loop to attach the pool to.
            self.app._setup_executor()
            await self.app.cable.start()

        loop.run_until_complete(start())

    def __rsgi_del__(self, loop):
        loop.run_until_complete(self.app.cable.stop())
        self.app._shutdown_executor()

    async def __rsgi__(self, scope, protocol):
        if scope.proto != "http":
            protocol.close(1003)
            return
        host, _, port = scope.server.rpartition(":")
        headers = [
            (k.encode("latin-1"), v.encode("latin-1"))
            for k, v in scope.headers.items()
        ]
        asgi_scope = {
            "type": "http",
            "app": self.app,
            "http_version": scope.http_version,
            "method": scope.method,
            "path": scope.path,
            "query_string": scope.query_string.encode(),
            "root_path": "",
            "scheme": scope.scheme,
            "server": (host, int(port)),
            "headers": headers,
        }
        current.app = self.app

        body_read = False

        async def receive():
            nonlocal body_read
            if body_read:
                return {"type": "http.disconnect"}
            body_read = True
            return {"type": "http.request", "body": await protocol(), "more_body": False}

        response = await self.app._do_request(asgi_scope, receive)
        status, headers, body = response.prepare()
        headers = [(k.decode("latin-1"), v.decode("latin-1")) for k, v in headers]
        if isinstance(body, bytes):
            protocol.response_bytes(status, headers, body)
            return
        transport = await protocol.response_stream(status, headers)
        chunks = iter(body)
        try:
            while True:
                chunk = await asyncio.to_thread(next, chunks, None)
                if chunk is None:
                    break
                await transport.send_bytes(chunk)
        finally:
            close = getattr(body, "close", None)
            if callable(close):
                close()


app = RsgiApp(proper_app)
