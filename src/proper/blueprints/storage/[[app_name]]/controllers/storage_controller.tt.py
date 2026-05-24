from io import BytesIO

from proper.errors import BadRequest, NotFound

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
        inline = obj.is_inline_content_type(obj.content_type)
        service_url = obj.service.service_url(obj, as_attachment=not inline)
        if service_url:
            self.response.redirect_to(service_url)
        else:
            obj.send_file()


@router.resource("storage/disk", pk="token")
class AttachmentDiskController(AppController):
    """Receives the bytes for an attachment whose service is local Disk.
    The client (e.g. Lexxy via DirectUpload)
    creates the metadata via `AttachmentController.create`, then PUTs
    the bytes to the URL the service returned.

    Authorization is the signed token in the URL - scoped with the
    `upload` salt so a leaked download URL can't be used to overwrite
    the file. Cross-app callers are blocked by the OriginProtection
    concern (same-site only by default).
    """

    def update(self):
        token = self.params.get("token")
        # `salt="upload"` matches what `Disk.direct_upload_url()` signs
        # with — a download token (default salt) won't resolve here, so
        # it can't be used to overwrite the bytes. The default `max_age`
        # (15 minutes) caps the leak window: a stolen upload URL only
        # works briefly after issuance, long enough for the browser's
        # PUT to complete even for large files on slow connections.
        obj = Attachment.resolve_token(token, salt="upload")
        if obj is None:
            raise NotFound

        # Reject the request before touching disk if the client lied about
        # how many bytes it would send. The size on the row was recorded
        # from the create step's `byte_size` and is what callers will
        # later see when reading the attachment back.
        body = self.request.body
        if obj.byte_size and len(body) != obj.byte_size:
            raise BadRequest(
                f"Body size {len(body)} doesn't match declared "
                f"byte_size {obj.byte_size}"
            )

        obj.service.upload(BytesIO(body), obj)
        return ""


@router.resource("storage", pk=None)
class AttachmentController(AppController):
    """The DirectUpload "create blob" endpoint. The client posts blob
    metadata, we register a pending `Attachment` row, and respond with a
    `direct_upload` envelope telling the client where (and with which
    headers) to PUT the bytes:

    Request body:
        {"blob": {"filename": ..., "content_type": ...,
                  "byte_size": ..., "checksum": "<base64-md5>"}}

    Response body:
        {"signed_id": "...", "attachable_sgid": "...",
         "filename": "...", "content_type": "...", "byte_size": ...,
         "previewable": true,
         "url": "/storage/redirect/...",
         "direct_upload": {"url": "...", "headers": {...}}}
    """

    def create(self):
        blob = self.params.get("blob") or {}
        filename = blob.get("filename")
        if not filename:
            raise BadRequest("Missing blob.filename")

        attachment = Attachment.create_pending_blob(
            filename=filename,
            content_type=blob.get("content_type") or "",
            byte_size=int(blob.get("byte_size") or 0),
            source=blob.get("blob_source") or "direct",
        )

        direct_upload = attachment.service.direct_upload_url(
            attachment,
            checksum=blob.get("checksum", ""),
        )

        return self.render(json={
            "id": str(attachment.id),
            "signed_id": attachment.generate_token(),
            # Lexxy serializes this as the `sgid` attribute on
            # `<proper-attachment>`; the renderer uses it to look the
            # attachment row up server-side.
            "attachable_sgid": str(attachment.id),
            "filename": attachment.filename,
            "content_type": attachment.content_type,
            "byte_size": attachment.byte_size,
            "previewable": attachment.content_type.startswith("image/"),
            "url": attachment.url,
            "direct_upload": direct_upload,
        })
