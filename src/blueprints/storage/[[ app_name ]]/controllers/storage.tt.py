from proper import request, response  # noqa
from proper.errors import NotFound

from [[ app_name ]].app import app
from [[ app_name ]].models import Attachment
from ..app import AppController


class Storage(AppController):
    def show(self):
        signed_pk = self.params["pk"]
        pk = app.storage.get_key(signed_pk)
        if not pk:
            raise NotFound

        obj = Attachment.get_or_none(Attachment.key == pk)
        if not obj:
            raise NotFound
        url = app.storage.get_url(obj)

        response.redirect_to(url)
