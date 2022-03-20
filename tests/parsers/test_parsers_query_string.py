from proper.helpers import MultiDict
from proper.request_wrapper.parse_query_string import parse_query_string


def test_parse_empty_query_string():
    assert parse_query_string("") == MultiDict()


def test_parse_query_string():
    query_string = (
        "colors=red&colors=green&colors=blue"
        "&empty1=&empty2&empty3="
        "&foo=bar"
        "&empty4=&empty4&empty4="
        "&empty5&empty5&empty5"
    )
    md = parse_query_string(query_string)
    assert md["colors"] == ["red", "green", "blue"]
    assert md["foo"] == ["bar"]
    assert md["empty1"] == [True]
    assert md["empty2"] == [True]
    assert md["empty3"] == [True]
    assert md["empty4"] == [True, True, True]
    assert md["empty5"] == [True, True, True]


def test_parse_encoded_query_string():
    md = parse_query_string("q=felíz+año+nuevo")
    assert md["q"] == ["felíz año nuevo"]

    md = parse_query_string("q=all%20the%20bells%20%26%20whistles")
    assert md["q"] == ["all the bells & whistles"]


def test_parse_malformed():
    md = parse_query_string("foo=bar&x=%&y=%+3")
    assert list(md.items()) == [("foo", ["bar"]), ("x", ["%"]), ("y", ["% 3"])]
