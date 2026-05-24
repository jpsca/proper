import typing as t


try:
    import boto3
    from botocore.client import Config as BotoConfig
except ImportError:
    boto3 = None  # type: ignore
    BotoConfig = None  # type: ignore

from .service import Service


if t.TYPE_CHECKING:
    from proper.app import App
    from proper.types import TAttachment, TUpload


class S3(Service):
    # Short enough that a leaked URL has limited blast radius; long enough
    # for the browser to fetch a large object on a slow connection. Tunable
    # per-service via the `url_expires_in` config key.
    DEFAULT_URL_EXPIRES_IN = 300

    def __init__(self, app: "App", **config: t.Any) -> None:
        if boto3 is None:
            raise ImportError("boto3 is required to use the S3 storage service.")
        self.bucket_name = config.pop("bucket")
        self.url_expires_in = int(
            config.pop("url_expires_in", self.DEFAULT_URL_EXPIRES_IN)
        )
        self.client = boto3.client(
            "s3",
            region_name=config.pop("region", None),
            endpoint_url=config.pop("endpoint", None),
            aws_access_key_id=config.pop("access_key_id", None),
            aws_secret_access_key=config.pop("secret_access_key", None),
            # Force SigV4 - required by AWS in newer regions, supported
            # everywhere else. Without this, `generate_presigned_url`
            # falls back to SigV2 against custom endpoints (MinIO, etc.).
            config=BotoConfig(signature_version="s3v4"),
        )
        super().__init__(app, **config)

    def _get_key(self, obj: "TAttachment") -> str:
        key = str(obj.id)
        filename = obj.filename or key
        return f"{key[:2]}/{key[2:4]}/{key}/{filename}"

    def upload(self, upload: "TUpload", obj: "TAttachment") -> None:
        file: t.BinaryIO = getattr(upload, "file", upload)  # type: ignore
        pos = file.tell()
        try:
            file.seek(0, 2)
            obj.byte_size = file.tell()
            file.seek(0)
            self.client.upload_fileobj(
                file,
                self.bucket_name,
                self._get_key(obj),
                ExtraArgs={"ContentType": obj.content_type},
            )
        finally:
            if not file.closed:
                file.seek(pos)

    def download(self, obj: "TAttachment") -> bytes:
        resp = self.client.get_object(
            Bucket=self.bucket_name,
            Key=self._get_key(obj),
        )
        return resp["Body"].read()

    def send_file(self, obj: "TAttachment", response, as_attachment: bool = False) -> None:
        data = self.download(obj)
        disposition = "attachment" if as_attachment else "inline"
        response.content_type = obj.content_type
        response.set_content_length(len(data))
        response.headers["content-disposition"] = (
            f'{disposition}; filename="{obj.filename}"'
        )
        response.body = data

    def purge(self, obj: "TAttachment") -> None:
        self.client.delete_object(
            Bucket=self.bucket_name,
            Key=self._get_key(obj),
        )

    def direct_upload_url(
        self, obj: "TAttachment", *, checksum: str = ""
    ) -> "dict[str, t.Any]":
        """A short-lived presigned PUT URL the browser uploads to directly
        - bytes never pass through the app.

        We pin `ContentType` and (when provided) `ContentMD5` into the
        signed params so the browser MUST send matching headers; S3
        rejects the PUT otherwise. This is both a tamper check and a
        soft cap on what the client can claim about the file.
        """
        params = {
            "Bucket": self.bucket_name,
            "Key": self._get_key(obj),
            "ContentType": obj.content_type or "application/octet-stream",
        }
        if checksum:
            params["ContentMD5"] = checksum

        url = self.client.generate_presigned_url(
            "put_object",
            Params=params,
            ExpiresIn=self.url_expires_in,
        )
        headers = {"Content-Type": params["ContentType"]}
        if checksum:
            headers["Content-MD5"] = checksum
        return {"url": url, "headers": headers}

    def service_url(
        self, obj: "TAttachment", *, as_attachment: bool = False
    ) -> str:
        """A short-lived presigned GET URL for the object.

        We override the `Content-Disposition` and `Content-Type` headers
        of the redirected response via S3's `response-content-disposition`
        / `response-content-type` query params so the browser sees our
        chosen filename and the original mimetype - not the bare key the
        object was stored under.
        """
        disposition = "attachment" if as_attachment else "inline"
        filename = obj.filename or str(obj.id)
        return self.client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket_name,
                "Key": self._get_key(obj),
                "ResponseContentDisposition": (
                    f'{disposition}; filename="{filename}"'
                ),
                "ResponseContentType": obj.content_type,
            },
            ExpiresIn=self.url_expires_in,
        )
