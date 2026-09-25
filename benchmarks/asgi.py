"""ASGI entrypoint: `uvicorn benchmarks.asgi:app` or `granian --interface asgi benchmarks.asgi:app`."""
from .app import make_app


app = make_app()
