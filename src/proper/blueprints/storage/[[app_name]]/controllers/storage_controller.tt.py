from proper.errors import NotFound

from [[app_name]].models import Attachment
from [[app_name]].router import router
from .app_controller import AppController


@router.resource("storage/public", pk="pk")
class PublicAttachmentController(AppController):
    skip_authentication = True

    def show(self):
        pk = self.params.get("pk")
        obj = Attachment.get_public(pk)
        if not obj:
            raise NotFound
        obj.send_file()


@router.resource("storage", pk="token")
class AttachmentController(AppController):
    def show(self):
        token = self.params.get("token")
        obj = Attachment.get_signed(token, max_age=None)
        if not obj:
            raise NotFound
        # Add any extra guards here, like checking if the user has access
        # to the file, etc.
        obj.send_file()
