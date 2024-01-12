from proper import View
from ..app import app


class DBConnection:
    def before(self, view: View):
        if app.db:
            app.db.connect()
