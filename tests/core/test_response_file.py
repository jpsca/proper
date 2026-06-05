import io
from pathlib import Path
from unittest.mock import MagicMock, patch

from proper import Response
from proper import status as pstatus
from proper.core.response.file_wrapper import FileWrapper
from proper.helpers.asgi import make_test_scope


def _make_response(*, status=pstatus.ok, **scope_kw):
    """Build a Response with a valid ASGI scope."""
    scope = make_test_scope(**scope_kw)
    response = Response(scope, status=status)
    return response


def test_send_file_basic(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_text("Hello World")

    resp = _make_response()
    resp.send_file(f)
    assert "text/plain" in str(resp.content_type)
    assert "hello.txt" in resp.headers.get("content-disposition")
    assert "inline" in resp.headers.get("content-disposition")
    assert resp.content_length == 11


def test_send_file_as_attachment(tmp_path):
    f = tmp_path / "data.csv"
    f.write_text("a,b,c")

    resp = _make_response()
    resp.send_file(f, as_attachment=True)
    assert "attachment" in resp.headers.get("content-disposition")


def test_send_file_custom_mimetype(tmp_path):
    f = tmp_path / "data.bin"
    f.write_bytes(b"\x00\x01")

    resp = _make_response()
    resp.send_file(f, mimetype="application/octet-stream")
    assert resp.mimetype == "application/octet-stream"


def test_send_file_custom_download_name(tmp_path):
    f = tmp_path / "data.bin"
    f.write_bytes(b"\x00")

    resp = _make_response()
    resp.send_file(f, download_name="custom.bin")
    assert "custom.bin" in resp.headers.get("content-disposition")


def test_send_file_unicode_download_name(tmp_path):
    f = tmp_path / "data.bin"
    f.write_bytes(b"\x00")

    resp = _make_response()
    resp.send_file(f, download_name="resum\u00e9.pdf")
    disp = resp.headers.get("content-disposition")
    assert "filename*=UTF-8''" in disp


def test_send_file_x_sendfile(tmp_path):
    subdir = tmp_path / "app"
    subdir.mkdir()
    f = tmp_path / "file.txt"
    f.write_text("content")

    mock_app = MagicMock()
    mock_app.root_path = subdir  # parent is tmp_path
    scope = make_test_scope()
    scope["app"] = mock_app

    resp = Response(scope)
    resp.send_file(f, x_sendfile_header="X-Accel-Redirect")
    assert resp.headers.get("X-Accel-Redirect") == "/file.txt"
    assert resp.body == ""


def test_send_file_gzip_encoding_inline(tmp_path):
    f = tmp_path / "archive.tar.gz"
    f.write_bytes(b"\x00" * 10)

    resp = _make_response()
    resp.send_file(f)
    assert resp.content_encoding == ["gzip"]


def test_send_file_gzip_encoding_attachment(tmp_path):
    f = tmp_path / "archive.tar.gz"
    f.write_bytes(b"\x00" * 10)

    resp = _make_response()
    resp.send_file(f, as_attachment=True)
    assert resp.content_encoding is None


def test_send_file_unknown_mimetype(tmp_path):
    f = tmp_path / "file.unknownext"
    f.write_bytes(b"data")

    resp = _make_response()
    resp.send_file(f)
    assert resp.mimetype == "application/octet-stream"


def test_send_file_skips_content_length_when_st_size_none(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_text("Hello")

    fake_stat = MagicMock()
    fake_stat.st_size = None
    fake_stat.st_mtime = 1704067200.0

    resp = _make_response()
    with patch.object(Path, "stat", return_value=fake_stat):
        resp.send_file(f)
    assert resp.content_length is None


def test_send_file_body_is_file_wrapper(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_text("Hello")

    resp = _make_response()
    resp.send_file(f)
    assert isinstance(resp.body, FileWrapper)


def test_send_file_sets_last_modified(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_text("Hello")

    resp = _make_response()
    resp.send_file(f)
    assert resp.last_modified is not None


def test_filewrapper_iter():
    f = io.BytesIO(b"hello world")
    wrapper = FileWrapper(f, block_size=5)
    chunks = list(wrapper)
    assert b"".join(chunks) == b"hello world"


def test_filewrapper_close():
    f = io.BytesIO(b"data")
    wrapper = FileWrapper(f)
    wrapper.close()
    assert f.closed


def test_filewrapper_close_no_close_method():
    class NoClose:
        def read(self, n):
            return b""

    wrapper = FileWrapper(NoClose())  # type: ignore
    wrapper.close()


def test_filewrapper_seekable_true():
    f = io.BytesIO(b"data")
    wrapper = FileWrapper(f)
    assert wrapper.seekable() is True


def test_filewrapper_seekable_false():
    class NoSeek:
        def read(self, n):
            return b""

    wrapper = FileWrapper(NoSeek())  # type: ignore
    assert wrapper.seekable() is False


def test_filewrapper_seekable_via_seek_method():
    class HasSeek:
        def read(self, n):
            return b""

        def seek(self, *args):
            pass

    wrapper = FileWrapper(HasSeek())  # type: ignore
    assert wrapper.seekable() is True


def test_filewrapper_seek():
    f = io.BytesIO(b"hello world")
    wrapper = FileWrapper(f)
    wrapper.seek(5)
    assert f.tell() == 5


def test_filewrapper_seek_no_seek_method():
    class NoSeek:
        def read(self, n):
            return b""

    wrapper = FileWrapper(NoSeek())  # type: ignore
    wrapper.seek(5)


def test_filewrapper_tell():
    f = io.BytesIO(b"hello")
    wrapper = FileWrapper(f)
    assert wrapper.tell() == 0
    f.read(3)
    assert wrapper.tell() == 3


def test_filewrapper_tell_no_tell_method():
    class NoTell:
        def read(self, n):
            return b""

    wrapper = FileWrapper(NoTell())  # type: ignore
    assert wrapper.tell() is None


def test_filewrapper_iter_returns_self():
    f = io.BytesIO(b"")
    wrapper = FileWrapper(f)
    assert iter(wrapper) is wrapper


def test_filewrapper_empty_read_stops():
    f = io.BytesIO(b"")
    wrapper = FileWrapper(f)
    chunks = list(wrapper)
    assert chunks == []
