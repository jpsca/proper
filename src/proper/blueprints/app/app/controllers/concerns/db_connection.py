from proper import Controller

from app.main import app


class DBConnection:
    def before(self, co: Controller):
        if app.db:
            app.db.connect()
