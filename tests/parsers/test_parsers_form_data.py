from io import BytesIO

import pytest
import ujson

from proper.parsers import parse_form_data


def test_parse_json():
    source = {
        "menu": {
            "id": "file",
            "value": "File",
            "popup": {
                "menuitem": [
                    {"value": "New", "onclick": "CreateNewDoc()"},
                    {"value": "Open", "onclick": "OpenDoc()"},
                    {"value": "Close", "onclick": "CloseDoc()"},
                ]
            },
        }
    }
    body = ujson.dumps(source).encode("utf8")
    stream = BytesIO(body)
    content_type = "application/json"
    content_length = len(body)

    body = parse_form_data(stream, content_type, content_length)
    assert body == source


def test_parse_bad_json_body():
    body = b"bad json is bad"
    stream = BytesIO(body)
    content_type = "application/json"
    content_length = len(body)

    with pytest.raises(ValueError):
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
    assert md["empty1"] == [True]
    assert md["empty2"] == [True]
    assert md["empty3"] == [True]
    assert md["empty4"] == [True, True, True]
    assert md["empty5"] == [True, True, True]
