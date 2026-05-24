import typing as t


if t.TYPE_CHECKING:
    from proper.app import App
    from proper.types import TAttachment, TUpload


class Service:
    """Abstract class serving as an interface for concrete services."""

    public: bool = False

    def __init__(self, app: "App", **config: t.Any) -> None:
        self.public = bool(config.pop("public", False))
        self.config = config

    def upload(self, upload: "TUpload", obj: "TAttachment") -> None:
        raise NotImplementedError

    def download(self, obj: "TAttachment") -> bytes:
        raise NotImplementedError

    def send_file(self, obj: "TAttachment", response, as_attachment: bool = False) -> None:
        raise NotImplementedError

    def purge(self, obj: "TAttachment") -> None:
        raise NotImplementedError

    def service_url(
        self, obj: "TAttachment", *, as_attachment: bool = False
    ) -> "str | None":
        """A URL the client can be redirected to to fetch the bytes directly
        from the underlying storage (e.g. a presigned S3 link). Override on
        remote services where this is cheaper than streaming through the
        app.

        Returning `None` is fine: the redirect controller falls back to the
        proxy path so URLs always work regardless of service support.
        """
        return None

    def direct_upload_url(
        self, obj: "TAttachment", *, checksum: str = ""
    ) -> "dict[str, t.Any]":
        """Return where (and with which headers) the client should PUT the
        file bytes for a freshly-created pending blob.

        Shape: `{"url": "...", "headers": {"Content-Type": "...", ...}}`.

        For remote services (S3, GCS, ...) this is a presigned PUT URL the
        browser hits directly. For local services (Disk) it's the app's
        own bytes-receiving endpoint.

        Implementations MUST set `Content-Type`. If the client supplies a
        base64 MD5 `checksum`, propagate it as `Content-MD5` so the
        backing store can verify the upload (S3 enforces, Disk can too).
        """
        raise NotImplementedError
