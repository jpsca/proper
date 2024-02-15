from proper import View

from [[ app_name ]].app import app


class DBConnection:
    def before(self, view: View):
        if app.db:
            app.db.connect()

    def after(self, view: View):
        pass
