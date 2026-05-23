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


@router.resource("storage/proxy", pk="token")
class AttachmentProxyController(AppController):
    """Streams the attachment bytes through the app. Use when you need a
    stable URL under your own domain (CDN caching, app-controlled
    headers, auth gating beyond the signed token).
    """

    def show(self):
        token = self.params.get("token")
        obj = Attachment.get_signed(token, max_age=None)
        if not obj:
            raise NotFound
        # Add any extra guards here, like checking if the user has access
        # to the file, etc.
        obj.send_file()


@router.resource("storage/redirect", pk="token")
class AttachmentRedirectController(AppController):
    """302s to the storage service's native URL (e.g. a presigned S3
    link) when the service implements `service_url()`. Falls back to
    streaming the bytes when it doesn't (the disk service, etc.) so the
    URL keeps working regardless of where the file lives.
    """

    def show(self):
        token = self.params.get("token")
        obj = Attachment.get_signed(token, max_age=None)
        if not obj:
            raise NotFound
        # Add any extra guards here, like checking if the user has access
        # to the file, etc.
        inline = obj._is_inline_content_type(obj.content_type)
        service_url = obj._service.service_url(obj, as_attachment=not inline)
        if service_url:
            self.response.redirect_to(service_url)
        else:
            obj.send_file()


# Extension point for addons that need to add actions at `/storage` (the
# rich-text addon appends a `create` action here for its upload endpoint).
# Keep this class last in the file so `.append.py` files land their
# methods inside it.
@router.resource("storage", pk=None)
class AttachmentController(AppController):
    pass
