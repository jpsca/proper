from io import BytesIO

from proper.helpers import copy_file


def test_basic():
    src = BytesIO(b"hello world")
    dst = BytesIO()
    size = copy_file(src, dst)
    assert size == 11
    assert dst.getvalue() == b"hello world"

def test_maxread():
    src = BytesIO(b"hello world")
    dst = BytesIO()
    size = copy_file(src, dst, maxread=5)
    assert size == 5
    assert dst.getvalue() == b"hello"

def test_empty():
    src = BytesIO(b"")
    dst = BytesIO()
    size = copy_file(src, dst)
    assert size == 0
