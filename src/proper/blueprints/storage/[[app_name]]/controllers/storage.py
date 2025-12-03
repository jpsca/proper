from proper.errors import NotFound

from ..main import app
from ..router import router

from .base import BaseController, PrivateController


class PublicStorageController(BaseController):
    @router.get("/storage/public/<pk>")
    def show(self):
        pk = self.params.get("pk")
        obj = app.storage.get_public_attachment(pk)
        if not obj:
            raise NotFound
        obj.send_file()


class StorageController(PrivateController):
    @router.get("/storage/<pk>")
    def show(self):
        signed_pk = self.params.get("pk")
        obj = app.storage.get_attachment(signed_pk, max_age=None)
        if not obj:
            raise NotFound
        # Add any extra guards here, like checking if the user has access
        # to the file, etc.
        obj.send_file()
