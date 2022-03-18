import json
from io import BytesIO

import pytest

from proper import errors
from proper.request.parse_form_data import parse_form_data


def test_parse_json():
    source = {
        "id": "file",
        "value": "File",
        "menuitem": [
            {"value": "New", "onclick": "CreateNewDoc()"},
            {"value": "Open", "onclick": "OpenDoc()"},
            {"value": "Close", "onclick": "CloseDoc()"},
        ]
    }
    body = json.dumps(source).encode("utf8")
    stream = BytesIO(body)
    content_type = "application/json"
    content_length = len(body)

    md = parse_form_data(stream, content_type, content_length)
    assert md["id"] == ["file"]
    assert md["value"] == ["File"]
    assert md["menuitem"] == [[
        {"value": "New", "onclick": "CreateNewDoc()"},
        {"value": "Open", "onclick": "OpenDoc()"},
        {"value": "Close", "onclick": "CloseDoc()"},
    ]]


def test_parse_bad_json_body():
    body = b"bad json is bad"
    stream = BytesIO(body)
    content_type = "application/json"
    content_length = len(body)

    with pytest.raises(errors.BadRequest):
        parse_form_data(stream, content_type, content_length)


def test_parse_urlencoded():
    body = (
        "colors=red&colors=green&colors=blue"
        "&empty1=&empty2&empty3="
        "&foo=bar"
        "&empty4=&empty4&empty4="
        "&empty5&empty5&empty5"
    ).encode("utf8")
    stream = BytesIO(body)
    content_type = "application/x-www-form-urlencoded"
    content_length = len(body)
    md = parse_form_data(stream, content_type, content_length)
    assert md["colors"] == ["red", "green", "blue"]
    assert md["foo"] == ["bar"]
    assert md["empty1"] == [""]
    assert md["empty2"] == [""]
    assert md["empty3"] == [""]
    assert md["empty4"] == ["", "", ""]
    assert md["empty5"] == ["", "", ""]
