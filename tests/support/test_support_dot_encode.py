from proper.support import Dot


class UpperDot(Dot):
    def _key_encode(self, key):
        if isinstance(key, str):
            key = key.upper()
        return key


def test_encode_set():
    dot = UpperDot()
    dot["hello"] = "a"

    assert "hello" in dot
    assert "HELLO" in dot
    assert "hEllO" in dot
    assert dot.HELLO == "a"


def test_encode_setdefault():
    dot = UpperDot()
    dot.setdefault("hello", "a")

    assert dot.HELLO == "a"


def test_encode_update_dict():
    dot = UpperDot({"a": "aa"})
    dot.update({"a": "aaa", "b": "bbb"})

    assert dot.A == "aaa"
    assert dot.B == "bbb"


def test_encode_update_iter():
    dot = UpperDot({"a": "aa"})
    dot.update([("a", "aaa"), ("b", "bbb")])

    assert dot.A == "aaa"
    assert dot.B == "bbb"


def test_encode():
    dot = UpperDot({"a": "aaa", "b": "bbb"})

    assert list(dot.items()) == [("A", "aaa"), ("B", "bbb")]
