from proper import request, response  # noqa
from proper.errors import NotFound

from [[ app_name ]].app import app
from ..app import AppController


class Storage(AppController):
    def show(self):
        signed_pk = self.params["pk"]
        obj = app.storage.get_attachment(signed_pk, max_age=None)
        if not obj:
            raise NotFound

        obj.send_file()
