import mimetypes
import random
import typing as t
from io import BytesIO
from pathlib import Path

from proper.constants import DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT, RESTORE
from proper.helpers import DotDict
from proper.request import make_test_env


if t.TYPE_CHECKING:
    from proper.types import TWSGIEnvironment

    from ..response import Response


def to_bytes(value, charset="latin1"):
    if isinstance(value, str):
        return value.encode(charset)
    return value


class AppTest:
    def do_request(self, environ: "TWSGIEnvironment") -> "Response":
        raise NotImplementedError

    def get(
        self,
        url: str,
        *,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> DotDict:
        """
        Do a GET request given the url path.

        Arguments:

        - url:
            A full URL or a path

        - params:
            A dictionary that will be encoded
            into a query string. You may also include a URL query
            string on the `url`.

        - headers:
            Extra headers to send.

        """
        return self._do_test_request(url, method=GET, params=params, headers=headers)

    def head(
        self,
        url: str,
        *,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> DotDict:
        """
        Do a HEAD request. Similar to `AppTest.get`.
        """
        return self._do_test_request(url, method=HEAD, params=params, headers=headers)

    def post(
        self,
        url: str,
        *,
        body: dict | str | bytes | BytesIO = b"",
        upload_files: list[tuple[str, str | Path]] | None = None,
        headers: dict | None = None,
    ) -> DotDict:
        """
        Do a POST request given the url path.

        Arguments:

        - url:
            A full URL or a path

        - body:
            Are put in the body of the request. If body is a dict
            it will be urlencoded. If it is a string, it will not
            be encoded, but placed in the body directly.
            If `upload_files` is also used, `body` must be a dict.

        - upload_files:
            It should be a list of `(fieldname, filename)`. The file
            contents will be read from disk.

        - headers:
            Extra headers to send.

        """
        return self._do_test_request(
            url, method=POST, body=body, upload_files=upload_files, headers=headers
        )

    def patch(
        self,
        url: str,
        *,
        body: dict | str | bytes | BytesIO = b"",
        upload_files: list[tuple[str, str | Path]] | None = None,
        headers: dict | None = None,
    ) -> DotDict:
        """
        Do a PATCH request. Similar to `AppTest.post`.
        """
        return self._do_test_request(
            url, method=PATCH, body=body, upload_files=upload_files, headers=headers
        )

    def put(
        self,
        url: str,
        *,
        body: dict | str | bytes | BytesIO = b"",
        upload_files: list[tuple[str, str | Path]] | None = None,
        headers: dict | None = None,
    ) -> DotDict:
        """
        Do a PUT request. Similar to `AppTest.post`.
        """
        return self._do_test_request(
            url, method=PUT, body=body, upload_files=upload_files, headers=headers
        )

    def query(
        self,
        url: str,
        *,
        body: dict | str | bytes | BytesIO = b"",
        upload_files: list[tuple[str, str | Path]] | None = None,
        headers: dict | None = None,
    ) -> DotDict:
        """
        Do a QUERY request. Similar to `AppTest.post`but.
        """
        return self._do_test_request(
            url, method=PUT, body=body, upload_files=upload_files, headers=headers
        )

    def options(
        self,
        url: str,
        *,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> DotDict:
        """
        Do a OPTIONS request. Similar to `AppTest.get`.
        """
        return self._do_test_request(
            url, method=OPTIONS, params=params, headers=headers
        )

    def delete(
        self,
        url: str,
        *,
        body: dict | str | bytes | BytesIO = b"",
        upload_files: list[tuple[str, str | Path]] | None = None,
        headers: dict | None = None,
    ) -> DotDict:
        """
        Do a DELETE request. Similar to `AppTest.post`.
        """
        return self._do_test_request(
            url, method=DELETE, body=body, upload_files=upload_files, headers=headers
        )

    def restore(
        self,
        url: str,
        *,
        body: dict | str | bytes | BytesIO = b"",
        upload_files: list[tuple[str, str | Path]] | None = None,
        headers: dict | None = None,
    ) -> DotDict:
        """
        Do a RESTORE request. Similar to `AppTest.post`.
        """
        return self._do_test_request(
            url, method=RESTORE, body=body, upload_files=upload_files, headers=headers
        )

    # PRIVATE

    def _do_test_request(
        self,
        url: str,
        *,
        method=GET,
        params: dict | None = None,
        body: dict | str | bytes | BytesIO = b"",
        upload_files: list[tuple[str, str | Path]] | None = None,
        headers: dict | None = None,
    ):
        if params is None:
            params = {}
        headers = headers or {}
        headers["REQUEST_METHOD"] = method.upper()

        if upload_files:
            if not isinstance(body, dict):
                body = {}
            content_type, body = self._encode_multipart(params=body, upload_files=upload_files)
            headers["CONTENT_TYPE"] = content_type

        environ = make_test_env(url, body=body, params=params, **headers)

        response = self.do_request(environ)
        response.prepare_body()
        return DotDict(
            status=response.status,
            headers=dict(response.get_headers_list()),
            body=response.body,
            mimetype=response.mimetype,
            content_type=response.content_type,
        )

    def _encode_multipart(
        self,
        params: dict | None = None,
        upload_files: list[tuple[str, str | Path]] | None = None,
    ):
        """
        Encodes a set of parameters (name/value list) and
        a set of files (a list of (name, filename, file_body, mimetype)) into a
        typical POST body, returning the (content_type, body).

        """
        boundary: bytes = to_bytes(str(random.random()))[2:]
        boundary = b"----------b_o_u_n_d_a_r_y" + boundary + b"$"
        lines = []

        def _append_file(skey: str, filename: str | Path):
            key = skey.encode("ascii")
            filepath = Path(filename)

            ftype = mimetypes.guess_type(filename)[0]
            ctype = to_bytes(ftype) if ftype else b"application/octet-stream"

            lines.extend(
                [
                    b"--" + boundary,
                    b"Content-Disposition: form-data; "
                    + b'name="'
                    + key
                    + b'"; filename="'
                    + to_bytes(str(filename))
                    + b'"',
                    b"Content-Type: " + ctype,
                    b"",
                    filepath.read_bytes(),
                ]
            )

        params = params or {}
        for key, value in params:
            if isinstance(key, str):
                key = key.encode("ascii")

            if isinstance(value, int):
                value = str(value).encode("utf8")
            elif isinstance(value, str):
                value = value.encode("utf8")
            elif not isinstance(value, (bytes, str)):
                raise ValueError(
                    (
                        "Value for field {} is a {} ({}). "
                        "It must be str, bytes or an int"
                    ).format(key, type(value), value)
                )
            lines.extend(
                [
                    b"--" + boundary,
                    b'Content-Disposition: form-data; name="' + key + b'"',
                    b"",
                    value,
                ]
            )

        if upload_files:
            for key, filename in upload_files:
                _append_file(key, filename)

        lines.extend([b"--" + boundary + b"--", b""])
        body = b"\r\n".join(lines)
        content_type = "multipart/form-data; boundary=%s" % boundary.decode("ascii")
        return content_type, body
