import pytest

from proper.request.forwarded import parse_forwarded


def test_single_forwarded_header() -> None:
    header = "by=identifier;for=identifier;host=identifier;proto=identifier"
    values = parse_forwarded(header)
    assert values[0]["by"] == "identifier"
    assert values[0]["for"] == "identifier"
    assert values[0]["host"] == "identifier"
    assert values[0]["proto"] == "identifier"


@pytest.mark.parametrize(
    "fw_in, fw_out",
    [
        ("1.2.3.4", "1.2.3.4"),
        ('"[2001:db8:cafe::17]"', "[2001:db8:cafe::17]"),
    ],
)
def test_forwarded_node_identifier(fw_in: str, fw_out: str):
    header = f"for={fw_in}"
    values = parse_forwarded(header)
    assert values[0]["for"] == fw_out


def test_camelcase() -> None:
    header = "bY=identifier;fOr=identifier;HOst=identifier;pRoTO=identifier"
    values = parse_forwarded(header)
    assert values[0]["by"] == "identifier"
    assert values[0]["for"] == "identifier"
    assert values[0]["host"] == "identifier"
    assert values[0]["proto"] == "identifier"


def test_single_param() -> None:
    header = "BY=identifier"
    values = parse_forwarded(header)
    assert values[0]["by"] == "identifier"


def test_multiple_param() -> None:
    header = "By=identifier1,BY=identifier2,  By=identifier3 ,  BY=identifier4"
    values = parse_forwarded(header)
    assert len(values) == 4
    assert values[0]["by"] == "identifier1"
    assert values[1]["by"] == "identifier2"
    assert values[2]["by"] == "identifier3"
    assert values[3]["by"] == "identifier4"


def test_quoted_escaped() -> None:
    header = r'BY=identifier;pROTO="\lala lan\d\~ 123\!&"'
    values = parse_forwarded(header)
    assert values[0]["by"] == "identifier"
    assert values[0]["proto"] == "lala land~ 123!&"


def test_custom_param() -> None:
    header = r'BY=identifier;PROTO=https;SOME="other, \"value\""'
    values = parse_forwarded(header)
    print(values[0])
    assert len(values) == 1
    assert values[0]["by"] == "identifier"
    assert values[0]["proto"] == "https"
    assert values[0]["some"] == 'other, "value"'


def test_empty_params() -> None:
    # This is allowed by the grammar given in RFC 7239
    header = ";For=identifier;;PROTO=https;;;"
    values = parse_forwarded(header)
    assert values[0]["for"] == "identifier"
    assert values[0]["proto"] == "https"


def test_bad_separator() -> None:
    header = "BY=identifier PROTO=https"
    values = parse_forwarded(header)
    assert "proto" not in values[0]


def test_injection() -> None:
    """We might receive a header like this if we're sitting behind a reverse
    proxy that blindly appends a forwarded-element without checking
    the syntax of existing field-values. We should be able to recover
    the appended element anyway.
    """
    # This could be sent by an attacker, hoping to "shadow" the second header.
    header = 'for=_injected;by="'
    # This is added by our trusted reverse proxy.
    header = f"{header}, for=_real;by=_actual_proxy"
    values = parse_forwarded(header)
    assert len(values) == 2
    assert "by" not in values[0]
    assert values[1]["for"] == "_real"
    assert values[1]["by"] == "_actual_proxy"


def test_injection2() -> None:
    header = "very bad syntax, for=_real"
    values = parse_forwarded(header)
    assert len(values) == 2
    assert "for" not in values[0]
    assert values[1]["for"] == "_real"


def test_long_quoted_string() -> None:
    header = 'for="' + "\\\\" * 5000 + '"'
    values = parse_forwarded(header)
    assert values[0]["for"] == "\\" * 5000
