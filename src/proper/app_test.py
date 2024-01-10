import mimetypes
import random
from io import BytesIO
from pathlib import Path

from .constants import GET, HEAD, POST, PATCH, PUT, OPTIONS, DELETE, RESTORE
from .helpers import DotDict
from .request import make_test_env


def to_bytes(value, charset='latin1'):
    if isinstance(value, str):
        return value.encode(charset)
    return value


class AppTest:
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
            url:
                A full URL or a path

            params:
                A dictionary that will be encoded
                into a query string. You may also include a URL query
                string on the `url`.

            headers:
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
        params: dict | str | bytes | BytesIO | None = None,
        upload_files: tuple[str, str | Path] = tuple(),
        headers: dict | None = None,
    ) -> DotDict:
        """
        Do a POST request given the url path.

        Arguments:
            url:
                A full URL or a path

            params:
                Are put in the body of the request. If params is a dict
                it will be urlencoded. If it is a string, it will not
                be encoded, but placed in the body directly.

            upload_files:
                It should be a list of `(fieldname, filename)`. The file
                contents will be read from disk. If the `params` are not dict
                they will be ignored.

            headers:
                Extra headers to send.

        """
        return self._do_test_request(url, method=POST, params=params, upload_files=upload_files, headers=headers)

    def patch(
        self,
        url: str,
        *,
        params: dict | str | bytes | BytesIO | None = None,
        upload_files: tuple[str, str | Path] = tuple(),
        headers: dict | None = None,
    ) -> DotDict:
        """
        Do a PATCH request. Similar to `AppTest.post`.
        """
        return self._do_test_request(url, method=PATCH, params=params, upload_files=upload_files, headers=headers)

    def put(
        self,
        url: str,
        *,
        params: dict | str | bytes | BytesIO | None = None,
        upload_files: tuple[str, str | Path] = tuple(),
        headers: dict | None = None,
    ) -> DotDict:
        """
        Do a HEAD request. Similar to `AppTest.post`.
        """
        return self._do_test_request(url, method=PUT, params=params, upload_files=upload_files, headers=headers)

    def query(
        self,
        url: str,
        *,
        params: dict | str | bytes | BytesIO | None = None,
        headers: dict | None = None,
    ) -> DotDict:
        """
        Do a HEAD request. Similar to `AppTest.post` but without the capacity to upload files.
        """
        return self._do_test_request(url, method=PUT, params=params, headers=headers)

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
        return self._do_test_request(url, method=OPTIONS, params=params, headers=headers)

    def delete(
        self,
        url: str,
        *,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> DotDict:
        """
        Do a DELETE request. Similar to `AppTest.get`.
        """
        return self._do_test_request(url, method=DELETE, params=params, headers=headers)

    def restore(
        self,
        url: str,
        *,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> DotDict:
        """
        Do a RESTORE request. Similar to `AppTest.get`.
        """
        return self._do_test_request(url, method=RESTORE, params=params, headers=headers)

    # PRIVATE

    def _do_test_request(
        self,
        url: str,
        *,
        method=GET,
        params: dict | str | bytes | BytesIO | None = None,
        upload_files: tuple[str, str | Path] = tuple(),
        headers: dict | None = None,
    ):
        if params is None:
            params = {}
        headers = headers or {}
        headers["REQUEST_METHOD"] = method.upper()

        if upload_files:
            if not isinstance(params, dict):
                params = dict
            content_type, params = self._encode_multipart(params, upload_files or ())
            headers["CONTENT_TYPE"] = content_type

        environ = make_test_env(url, params=params, **headers)

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
        params: dict | str | bytes | BytesIO = None,
        files: tuple[str, str | Path] = tuple(),
    ):
        """
        Encodes a set of parameters (name/value list) and
        a set of files (a list of (name, filename, file_body, mimetype)) into a
        typical POST body, returning the (content_type, body).

        """
        boundary = to_bytes(str(random.random()))[2:]
        boundary = b"----------b_o_u_n_d_a_r_y" + boundary + b"$"
        lines = []

        def _append_file(key, filename):
            if isinstance(key, str):
                key = key.encode("ascii")
            filepath = Path(filename)
            fcontent = mimetypes.guess_type(filename)[0] or b"application/octet-stream"
            lines.extend(
                [
                    b"--" + boundary,
                    b"Content-Disposition: form-data; "
                    + b'name="'
                    + key
                    + b'"; filename="'
                    + to_bytes(filename)
                    + b'"',
                    b"Content-Type: " + fcontent,
                    b"",
                    filepath.read_bytes(),
                ]
            )

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

        for key, filename in files:
            _append_file(key, filename)

        lines.extend([b"--" + boundary + b"--", b""])
        body = b"\r\n".join(lines)
        boundary = boundary.decode("ascii")
        content_type = "multipart/form-data; boundary=%s" % boundary
        return content_type, body
