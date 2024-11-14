from proper.errors import NotFound

from app.main import app
from ..app import PrivateView


class Storage(PrivateView):
    def show(self):
        signed_pk = self.params.get("pk")
        obj = app.storage.get_attachment(signed_pk, max_age=None)
        if not obj:
            raise NotFound

        obj.send_file()
