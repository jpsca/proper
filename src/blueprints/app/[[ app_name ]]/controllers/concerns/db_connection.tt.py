from proper import Controller

from [[ app_name ]].app import app


class DBConnection:
    def before(self, co: Controller):
        if app.db:
            app.db.connect()
