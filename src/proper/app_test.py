import mimetypes
import random
import typing as t
from abc import abstractmethod
from io import BytesIO
from pathlib import Path
from urllib.parse import urlencode

from .constants import DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT, QUERY
from .helpers import DotDict
from .request import make_test_scope


if t.TYPE_CHECKING:
    from .response import Response
    from .types import TScope


def to_bytes(value, charset="latin1"):
    if isinstance(value, str):
        return value.encode(charset)
    return value


class AppTest:
    @abstractmethod
    def do_test_request(self, scope: "TScope", body: bytes = b"") -> "Response":
        ...

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
        Do a QUERY request. Similar to `AppTest.post`.
        """
        return self._do_test_request(
            url, method=QUERY, body=body, upload_files=upload_files, headers=headers
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
        extra_headers = []
        if headers:
            for name, val in headers.items():
                extra_headers.append((name, val))

        if upload_files:
            if not isinstance(body, dict):
                body = {}
            content_type, body_bytes = self._encode_multipart(
                params=body, upload_files=upload_files
            )
            extra_headers.append(("content-type", content_type))
        else:
            body_bytes = self._encode_body(body)
            if isinstance(body, dict) and body:
                extra_headers.append(
                    ("content-type", "application/x-www-form-urlencoded")
                )

        if body_bytes:
            extra_headers.append(("content-length", str(len(body_bytes))))

        scope = make_test_scope(
            url, method=method, params=params, headers=extra_headers
        )

        response = self.do_test_request(scope, body_bytes)
        resp_status, enc_headers, resp_body = response.prepare()
        if not isinstance(resp_body, bytes):
            resp_body = b"".join(resp_body)
        body_str = resp_body.decode(response.charset) if resp_body else ""
        result = DotDict(
            status=resp_status,
            body=body_str,
            mimetype=response.mimetype,
            content_type=response.content_type,
        )
        # Assign directly to avoid DotDict's deep-copy of dict values,
        # which breaks ResponseHeadersDict.
        dict.__setitem__(result, "headers", response.headers)
        return result

    @staticmethod
    def _encode_body(body: dict | str | bytes | BytesIO) -> bytes:
        if isinstance(body, dict):
            return urlencode(body).encode("utf-8") if body else b""
        if isinstance(body, str):
            return body.encode("utf-8")
        if isinstance(body, BytesIO):
            return body.read()
        return body

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
        for key, value in params.items():
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
