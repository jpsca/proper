import pytest

from proper.emails.utils import CachedDnsName, force_bytes, force_str, punycode, to_list


class TestPunycode:
    def test_ascii_domain(self):
        assert punycode("example.com") == "example.com"

    def test_unicode_domain(self):
        assert punycode("münchen.de") == "xn--mnchen-3ya.de"

    def test_already_ascii(self):
        assert punycode("xn--mnchen-3ya.de") == "xn--mnchen-3ya.de"


class TestForceStr:
    def test_str_passthrough(self):
        assert force_str("hello") == "hello"

    def test_bytes_to_str(self):
        assert force_str(b"hello") == "hello"

    def test_bytes_with_encoding(self):
        assert force_str("café".encode("latin-1"), encoding="latin-1") == "café"

    def test_strings_only_with_str(self):
        assert force_str("hello", strings_only=True) == "hello"

    def test_strings_only_with_bytes(self):
        assert force_str(b"hello", strings_only=True) == "hello"

    def test_strings_only_with_non_string(self):
        result = force_str(42, strings_only=True)
        assert result == 42

    def test_non_string_without_strings_only(self):
        with pytest.raises(TypeError):
            force_str(42)


class TestForceBytes:
    def test_bytes_passthrough_utf8(self):
        assert force_bytes(b"hello") == b"hello"

    def test_bytes_re_encode(self):
        result = force_bytes(b"caf\xc3\xa9", encoding="latin-1")
        assert result == "café".encode("latin-1")

    def test_str_to_bytes(self):
        assert force_bytes("hello") == b"hello"

    def test_str_to_bytes_with_encoding(self):
        assert force_bytes("café", encoding="latin-1") == "café".encode("latin-1")

    def test_strings_only_with_non_string(self):
        assert force_bytes(42, strings_only=True) == 42

    def test_non_string_converts(self):
        assert force_bytes(42) == b"42"

    def test_memoryview(self):
        assert force_bytes(memoryview(b"hello")) == b"hello"


class TestToList:
    def test_none(self):
        assert to_list(None) == []

    def test_string(self):
        assert to_list("foo@example.com") == ["foo@example.com"]

    def test_list(self):
        assert to_list(["a", "b"]) == ["a", "b"]

    def test_tuple(self):
        assert to_list(("a", "b")) == ["a", "b"]

    def test_generator(self):
        assert to_list(x for x in ["a", "b"]) == ["a", "b"]

    def test_empty_list(self):
        assert to_list([]) == []


class TestCachedDnsName:
    def test_get_fqdn_returns_string(self):
        dns = CachedDnsName()
        fqdn = dns.get_fqdn()
        assert isinstance(fqdn, str)

    def test_str_returns_fqdn(self):
        dns = CachedDnsName()
        assert str(dns) == dns.get_fqdn()

    def test_caches_result(self):
        dns = CachedDnsName()
        first = dns.get_fqdn()
        second = dns.get_fqdn()
        assert first == second
        assert hasattr(dns, "_fqdn")
