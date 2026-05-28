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
    from proper.storage import _Attachment
    from proper.types import TUpload


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
        # Path-style prefix for the bucket's public objects. Used by
        # `service_url()` when `public: True`. Subclass and override
        # `service_url()` to point at a CloudFront / custom domain.
        self._public_url_prefix = (
            f"{self.client.meta.endpoint_url.rstrip('/')}/{self.bucket_name}"
        )

    def _get_key(self, att: "_Attachment") -> str:
        key = str(att.id)
        filename = att.filename or key
        return f"{key[:2]}/{key}/{filename}"

    def upload(self, upload: "TUpload", att: "_Attachment") -> None:
        file: t.BinaryIO = getattr(upload, "file", upload)  # type: ignore
        pos = file.tell()
        try:
            file.seek(0, 2)
            att.byte_size = file.tell()
            file.seek(0)
            extra_args: dict[str, t.Any] = {"ContentType": att.content_type}
            if self.public:
                # Public-read ACL is required for the bucket's native URL
                # to be reachable without signing. The bucket itself must
                # allow object-level ACLs (S3: "Object Ownership" set to
                # "BucketOwnerPreferred" or "ObjectWriter").
                extra_args["ACL"] = "public-read"
            self.client.upload_fileobj(
                file,
                self.bucket_name,
                self._get_key(att),
                ExtraArgs=extra_args,
            )
        finally:
            if not file.closed:
                file.seek(pos)

    def download(self, att: "_Attachment") -> bytes:
        resp = self.client.get_object(
            Bucket=self.bucket_name,
            Key=self._get_key(att),
        )
        return resp["Body"].read()

    def send_file(self, att: "_Attachment", response, as_attachment: bool = False) -> None:
        data = self.download(att)
        disposition = "attachment" if as_attachment else "inline"
        response.content_type = att.content_type
        response.set_content_length(len(data))
        response.headers["content-disposition"] = (
            f'{disposition}; filename="{att.filename}"'
        )
        response.body = data

    def purge(self, att: "_Attachment") -> None:
        self.client.delete_object(
            Bucket=self.bucket_name,
            Key=self._get_key(att),
        )

    def service_url(
        self, att: "_Attachment", *, as_attachment: bool = False
    ) -> str:
        """For public services, return the bucket's native path-style URL
        with no expiry and no per-request header overrides. The browser
        decides disposition from `Content-Type` baked in at upload, so
        `as_attachment` is informational only on public services.

        For private services, return a short-lived presigned GET URL that
        overrides `Content-Disposition` and `Content-Type` so the browser
        sees our chosen filename and the original mimetype - not the bare
        key the object was stored under.
        """
        if self.public:
            return f"{self._public_url_prefix}/{self._get_key(att)}"

        disposition = "attachment" if as_attachment else "inline"
        filename = att.filename or str(att.id)
        return self.client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket_name,
                "Key": self._get_key(att),
                "ResponseContentDisposition": (
                    f'{disposition}; filename="{filename}"'
                ),
                "ResponseContentType": att.content_type,
            },
            ExpiresIn=self.url_expires_in,
        )

    def direct_upload_url(
        self, att: "_Attachment", *, checksum: str = ""
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
            "Key": self._get_key(att),
            "ContentType": att.content_type or "application/octet-stream",
        }
        if self.public:
            params["ACL"] = "public-read"
        if checksum:
            params["ContentMD5"] = checksum

        url = self.client.generate_presigned_url(
            "put_object",
            Params=params,
            ExpiresIn=self.url_expires_in,
        )
        headers = {"Content-Type": params["ContentType"]}
        if self.public:
            # The browser MUST send this header for the signed PUT to
            # succeed - S3 verifies it against the signed `ACL` param.
            headers["x-amz-acl"] = "public-read"
        if checksum:
            headers["Content-MD5"] = checksum
        return {"url": url, "headers": headers}
