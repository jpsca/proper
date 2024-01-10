from proper import Controller
from ..app import app


class DBConnection:
    def before(self, controller: Controller):
        if app.db:
            app.db.connect()
