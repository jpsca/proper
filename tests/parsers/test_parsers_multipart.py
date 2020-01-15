from io import BytesIO

import pytest

from proper.parsers import parse_form_data


REQUESTS = [
    (
        "multipart-png-tbla.txt",
        "disk lookup.png",
        "folder.png",
        "--text\n--with boundary\n--lookalikes--",
    ),
    ("multipart-svg-jpg-tnull.txt", "photo.jpg", "home.svg", ""),
    (
        "multipart-webkit-png-tacc.txt",
        "folder.png",
        "disk lookup.png",
        "loremipsdj áé ñ öäü",
    ),
]


def multipart(body):
    # first line, without the first two dashes
    boundary = body.split(b"\n", 1)[0].strip(b"\r")[2:].decode("utf8")
    return {
        "stream": BytesIO(body),
        "content_type": "multipart/form-data; boundary=" + boundary,
        "content_length": len(body),
    }


@pytest.mark.parametrize("req_file, file1, file2, text", REQUESTS)
def test_multipart_upload(assets_path, app, req_file, file1, file2, text):
    body = (assets_path / req_file).read_bytes()
    md = parse_form_data(**multipart(body))
    assert "file1" in md
    assert "file2" in md
    assert "text" in md
    assert md.get("file1").filename == file1
    assert md.get("file2").filename == file2
    assert md.get("text") == text
