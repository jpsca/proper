from io import BytesIO

from proper.errors import BadRequest, NotFound
from proper.units import MINUTES

from [[app_name]].models import Attachment
from [[app_name]].router import router
from .app_controller import AppController


class StorageRedirectController(AppController):
    """Redirect to the storage service's native URL
    (e.g. a presigned S3 link) when the service
    implements `service_url()`.
    """
    skip_authentication = True

    @router.get("storage/redirect/:token/:filename")
    def show(self):
        attachment = Attachment.get_signed(
            self.params.get("token"),
            salt="redirect",
            max_age=None
        )
        if not attachment:
            raise NotFound

        # extra checks here

        service_url = attachment.service_url()
        if service_url:
            self.response.redirect_to(service_url)
        else:
            attachment.send_file()


class StorageProxyController(AppController):
    """Streams the attachment bytes through the app.
    """
    skip_authentication = True

    @router.get("storage/proxy/:token/:filename")
    def proxy(self):
        attachment = Attachment.get_signed(
            self.params.get("token"),
            salt="proxy",
            max_age=None
        )
        if not attachment:
            raise NotFound

        attachment.send_file()


@router.resource("storage/direct", pk="token")
class DirectUploadController(AppController):
    rate_limit = {"to": 10, "within": 1 * MINUTES}

    def create(self):
        """Registers a pending `Attachment` row and respond with
        a `direct_upload` envelope telling the client
        where (and with which headers) to PUT the bytes:

        Request body:
        ```
        {
            "blob": {
                "filename": ...,
                "content_type": ...,
                "byte_size": ...,
                "checksum": "<base64-md5>"
            }
        }
        ```

        Response body:
        ```
        {
            "signed_id": "...",
            "attachable_sgid": "...",
            "filename": "...",
            "content_type": "...",
            "byte_size": ...,
            "previewable": true/false,
            "url": "/storage/redirect/...",
            "direct_upload": {
                "url": "...",
                "headers": {...}
            }
        }
        ```
        """
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
        # For Disk, this will be
        # `url_for("DirectUpload.update", token=token, _full=True)`
        direct_upload = attachment.service.direct_upload_url(
            attachment,
            checksum=blob.get("checksum", ""),
        )

        return self.render(json={
            "id": str(attachment.id),
            "signed_id": attachment.generate_token(),
            "attachable_sgid": str(attachment.id),
            "filename": attachment.filename,
            "content_type": attachment.content_type,
            "byte_size": attachment.byte_size,
            "previewable": attachment.is_previewable,
            "url": attachment.url,
            "direct_upload": direct_upload,
        })

    def update(self):
        """Receives the bytes for an attachment whose service is local Disk.
        The client (e.g. Lexxy via DirectUpload) creates the metadata via
        `DirectUpload.create`, then PUTs the bytes to the URL the service returned.
        """
        token = self.params.get("token")
        # `salt="upload"` matches what `Disk.direct_upload_url()` signs with
        obj = Attachment.resolve_token(token, salt="upload")
        if obj is None:
            raise NotFound

        obj.service.upload(BytesIO(self.request.body), obj)
        return ""
