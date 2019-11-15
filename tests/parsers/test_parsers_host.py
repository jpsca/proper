from proper.parsers import parse_host as parse


def test_parse_empty_host():
    assert parse("") == ""


def test_parse_host():
    assert parse("::1") == "::1"
    assert parse("0.0.0.0") == "0.0.0.0"
    assert parse("0.0.0.0:3000") == "0.0.0.0"
    assert parse("localhost") == "localhost"

    ipv6_addr = "2800:200:e480:10d4:dc9e:51f0:f99e:b5f4"
    assert parse(ipv6_addr) == ipv6_addr
    assert parse("[" + ipv6_addr + "]") == ipv6_addr
    assert parse("[" + ipv6_addr + "]:34567") == ipv6_addr

    assert parse("142.93.243.145") == "142.93.243.145"
    assert parse("142.93.243.145:27070") == "142.93.243.145"

    assert parse("example.com") == "example.com"
    assert parse("proper.jpscaletti.com") == "proper.jpscaletti.com"
    assert parse("proper.jpscaletti.com:4000") == "proper.jpscaletti.com"
