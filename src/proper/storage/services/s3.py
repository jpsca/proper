import typing as t


try:
    import boto3
except ImportError:
    boto3 = None  # type: ignore

from .service import Service


if t.TYPE_CHECKING:
    from proper.app import App
    from proper.types import TAttachment, TUpload


class S3(Service):
    def __init__(self, app: "App", **config: t.Any) -> None:
        if boto3 is None:
            raise ImportError("boto3 is required to use the S3 storage service.")
        self.bucket_name = config.pop("bucket")
        self.client = boto3.client(
            "s3",
            region_name=config.pop("region", None),
            endpoint_url=config.pop("endpoint", None),
            aws_access_key_id=config.pop("access_key_id", None),
            aws_secret_access_key=config.pop("secret_access_key", None),
        )
        super().__init__(app, **config)

    def _get_key(self, obj: "TAttachment") -> str:
        key = str(obj.id)
        filename = obj.filename or key
        return f"{key[:2]}/{key[2:4]}/{filename}"

    def upload(self, filesto: "TUpload", obj: "TAttachment") -> None:
        file: t.BinaryIO = getattr(filesto, "file", filesto)  # type: ignore
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
            f"{disposition}; filename={obj.filename}"
        )
        response.body = data

    def purge(self, obj: "TAttachment") -> None:
        self.client.delete_object(
            Bucket=self.bucket_name,
            Key=self._get_key(obj),
        )
