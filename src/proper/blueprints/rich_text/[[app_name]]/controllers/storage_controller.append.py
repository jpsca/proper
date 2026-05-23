
    def create(self):
        """Receives a single file from the rich-text editor before the
        surrounding form is submitted, persists it as an `Attachment`,
        and returns its id + url for the editor to embed in the document.

        By default this inherits the app's authentication policy. If you
        want public uploads (e.g. an open comment form), add
        `skip_authentication = True`. If you want stricter rules (e.g.
        membership, role, quota), add `before` callbacks or override
        `create`.

        A periodic sweep (`tasks/rich_text_sweep.py`) deletes any
        `pending=True` upload older than a grace period — so users who
        close the tab without submitting don't leak files.
        """
        file = self.params.get("file")
        if not file or not getattr(file, "filename", None):
            raise BadRequest("Missing file")

        attachment = Attachment(
            file,
            source="rich_text",
            pending=True,
        )
        attachment.save()

        return self.render(json={
            "id": str(attachment.id),
            "url": attachment.url,
            "filename": attachment.filename,
            "content_type": attachment.content_type,
            "byte_size": attachment.byte_size,
            "previewable": attachment.content_type.startswith("image/"),
            # Token used by Lexxy as `:signed_id` when expanding the
            # `blob-url-template` on the `<lexxy-editor>`. Same token
            # `Attachment.url` would emit — `AttachmentRedirect.show`
            # (or `AttachmentProxy.show`) already resolves it.
            "signed_id": attachment.generate_token(),
        })


from proper.errors import BadRequest
from [[app_name]].models import Attachment