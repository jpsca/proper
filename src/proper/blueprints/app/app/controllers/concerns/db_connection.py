from proper import Controller

from app.main import app


class DBConnection:
    def __call__(self, co: Controller):
        if app.db:
            app.db.connect()
