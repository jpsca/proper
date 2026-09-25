"""Server entrypoint: `granian --interface rsgi benchmarks.rsgi:app`."""
from .app import make_app


app = make_app()
