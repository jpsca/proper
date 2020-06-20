from .core import core, import_app


@core.command(help="Run development server.")
def run():
    app = import_app()
    app.run_server(app.config.host, app.config.port)
