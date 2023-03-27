# Based on the tests for multipart (0.2.4) by Marcel Hellkamp
# with modifications for the Proper project.
# Licensed under the MIT License.
from io import BytesIO
from tempfile import NamedTemporaryFile

from proper.request import multipart as mp


# TODO: bufsize=10, line=1234567890--boundary\n
# TODO: bufsize < len(boundary) (should not be possible)
# TODO: bufsize = len(boundary)+5 (edge case)
# TODO: At least one test per possible exception (100% coverage)


def test_line_parser():
    for line in ("foo", ""):
        for ending in ("\n", "\r", "\r\n"):
            i = mp.MultipartParser(BytesIO(mp.to_bytes(line + ending)), "foo")
            i = next(i._lineiter())
            assert i == (mp.to_bytes(line), mp.to_bytes(ending))


def test_iterlines():
    data = "abc\ndef\r\nghi"
    result = [
        (mp.to_bytes("abc"), mp.to_bytes("\n")),
        (mp.to_bytes("def"), mp.to_bytes("\r\n")),
        (mp.to_bytes("ghi"), mp.to_bytes("")),
    ]
    i = mp.MultipartParser(BytesIO(mp.to_bytes(data)), "foo")._lineiter()
    assert list(i) == result


def test_iterlines_limit():
    data, limit = "abc\ndef\r\nghi", 10
    result = [
        (mp.to_bytes("abc"), mp.to_bytes("\n")),
        (mp.to_bytes("def"), mp.to_bytes("\r\n")),
        (mp.to_bytes("g"), mp.to_bytes("")),
    ]
    i = mp.MultipartParser(BytesIO(mp.to_bytes(data)), "foo", limit)._lineiter()
    assert list(i) == result

    data, limit = "abc\ndef\r\nghi", 8
    result = [
        (mp.to_bytes("abc"), mp.to_bytes("\n")),
        (mp.to_bytes("def"), mp.to_bytes("\r")),
    ]
    i = mp.MultipartParser(BytesIO(mp.to_bytes(data)), "foo", limit)._lineiter()
    assert list(i) == result


def test_iterlines_maxbuf():
    data, limit = "abcdefgh\nijklmnop\r\nq", 9
    result = [
        (mp.to_bytes("abcdefgh"), mp.to_bytes("\n")),
        (mp.to_bytes("ijklmnop"), mp.to_bytes("")),
        (mp.to_bytes(""), mp.to_bytes("\r\n")),
        (mp.to_bytes("q"), mp.to_bytes("")),
    ]
    i = mp.MultipartParser(
        BytesIO(mp.to_bytes(data)), "foo", buffer_size=limit
    )._lineiter()
    assert list(i) == result

    data, limit = ("X" * 3 * 1024) + "x\n", 1024
    result = [
        (mp.to_bytes("X" * 1024), mp.to_bytes("")),
        (mp.to_bytes("X" * 1024), mp.to_bytes("")),
        (mp.to_bytes("X" * 1024), mp.to_bytes("")),
        (mp.to_bytes("x"), mp.to_bytes("\n")),
    ]
    i = mp.MultipartParser(
        BytesIO(mp.to_bytes(data)), "foo", buffer_size=limit
    )._lineiter()
    assert list(i) == result


def test_copyfile():
    source = BytesIO(mp.to_bytes("abc"))
    target = BytesIO()
    assert mp.copy_file(source, target) == 3

    target.seek(0)
    assert target.read() == mp.to_bytes("abc")


def test_big_file():
    """If the size of an uploaded part exceeds memfile_limit,
    it is written to disk."""
    test_file = "abc" * 1024
    boundary = "---------------------------186454651713519341951581030105"
    request = BytesIO(
        mp.to_bytes("\r\n").join(
            map(
                mp.to_bytes,
                [
                    "--" + boundary,
                    'Content-Disposition: form-data; name="file1"; filename="random.png"',
                    "Content-Type: image/png",
                    "",
                    test_file,
                    "--" + boundary,
                    'Content-Disposition: form-data; name="file2"; filename="random.png"',
                    "Content-Type: image/png",
                    "",
                    test_file + "a",
                    "--" + boundary,
                    'Content-Disposition: form-data; name="file3"; filename="random.png"',
                    "Content-Type: image/png",
                    "",
                    test_file * 2,
                    "--" + boundary + "--",
                    "",
                ],
            )
        )
    )
    p = mp.MultipartParser(request, boundary, memfile_limit=len(test_file))
    try:
        assert p.get("file1").file.read() == mp.to_bytes(test_file)
        assert p.get("file1").is_buffered()
        assert p.get("file2").file.read() == mp.to_bytes(test_file + "a")
        assert not p.get("file2").is_buffered()
        assert p.get("file3").file.read() == mp.to_bytes(test_file * 2)
        assert not p.get("file3").is_buffered()
    finally:
        for part in p:
            part.close()


def test_get_all():
    """Test the get() and get_all() methods."""
    boundary = "---------------------------186454651713519341951581030105"
    request = BytesIO(
        mp.to_bytes("\r\n").join(
            map(
                mp.to_bytes,
                [
                    "--" + boundary,
                    'Content-Disposition: form-data; name="file1"; filename="random.png"',
                    "Content-Type: image/png",
                    "",
                    "abc" * 1024,
                    "--" + boundary,
                    'Content-Disposition: form-data; name="file1"; filename="random.png"',
                    "Content-Type: image/png",
                    "",
                    "def" * 1024,
                    "--" + boundary + "--",
                    "",
                ],
            )
        )
    )
    p = mp.MultipartParser(request, boundary)
    assert p.get("file1").file.read() == mp.to_bytes("abc" * 1024)
    assert p.get("file2") is None
    assert len(p.get_all("file1")) == 2
    assert p.get_all("file1")[1].file.read() == mp.to_bytes("def" * 1024)
    assert p.get_all("file1") == p.parts()


def test_file_seek():
    """The file object should be readable withoud a seek(0)."""
    test_file = "abc" * 1024
    boundary = "---------------------------186454651713519341951581030105"
    request = BytesIO(
        mp.to_bytes("\r\n").join(
            map(
                mp.to_bytes,
                [
                    "--" + boundary,
                    'Content-Disposition: form-data; name="file1"; filename="random.png"',
                    "Content-Type: image/png",
                    "",
                    test_file,
                    "--" + boundary + "--",
                    "",
                ],
            )
        )
    )
    p = mp.MultipartParser(request, boundary)
    assert p.get("file1").file.read() == mp.to_bytes(test_file)
    assert p.get("file1").value == test_file


def test_unicode_value():
    """The .value property always returns unicode"""
    test_file = "abc" * 1024
    boundary = "---------------------------186454651713519341951581030105"
    request = BytesIO(
        mp.to_bytes("\r\n").join(
            map(
                mp.to_bytes,
                [
                    "--" + boundary,
                    'Content-Disposition: form-data; name="file1"; filename="random.png"',
                    "Content-Type: image/png",
                    "",
                    test_file,
                    "--" + boundary + "--",
                    "",
                ],
            )
        )
    )
    p = mp.MultipartParser(request, boundary)
    assert p.get("file1").file.read() == mp.to_bytes(test_file)
    assert p.get("file1").value == test_file
    assert hasattr(p.get("file1").value, "encode")


def test_save_as():
    """save_as stores data in a file keeping the file position."""
    test_file = "abc" * 1024
    boundary = "---------------------------186454651713519341951581030105"
    request = BytesIO(
        mp.to_bytes("\r\n").join(
            map(
                mp.to_bytes,
                [
                    "--" + boundary,
                    'Content-Disposition: form-data; name="file1"; filename="random.png"',
                    "Content-Type: image/png",
                    "",
                    test_file,
                    "--" + boundary + "--",
                    "",
                ],
            )
        )
    )
    p = mp.MultipartParser(request, boundary)
    assert p.get("file1").file.read(1024) == mp.to_bytes(test_file)[:1024]

    tfn = NamedTemporaryFile(delete=False)
    p.get("file1").save_as(tfn.name)
    tf = open(tfn.name, "rb")
    assert tf.read() == mp.to_bytes(test_file)

    tf.close()
    assert p.get("file1").file.read() == mp.to_bytes(test_file)[1024:]


def test_multiline_header():
    """HTTP allows headers to be multiline."""
    test_file = mp.to_bytes("abc" * 1024)
    test_text = "Test text\n with\r\n ümläuts!"
    boundary = "---------------------------186454651713519341951581030105"
    request = BytesIO(
        mp.to_bytes("\r\n").join(
            map(
                mp.to_bytes,
                [
                    "--" + boundary,
                    "Content-Disposition: form-data;",
                    '\tname="file1"; filename="random.png"',
                    "Content-Type: image/png",
                    "",
                    test_file,
                    "--" + boundary,
                    "Content-Disposition: form-data;",
                    ' name="text"',
                    "",
                    test_text,
                    "--" + boundary + "--",
                    "",
                ],
            )
        )
    )
    p = mp.MultipartParser(request, boundary, encoding="utf8")
    assert p.get("file1").file.read() == test_file
    assert p.get("file1").filename == "random.png"
    assert p.get("text").value == test_text
