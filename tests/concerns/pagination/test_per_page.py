import pytest

from proper.concerns.pagination.geared_page import GearedPerPage
from proper.errors import InvalidPage


GEARED = [15, 30, 50, 100]


def test_size_of_progression():
    g = GearedPerPage(GEARED)
    assert [g.size_of(n) for n in range(1, 7)] == [15, 30, 50, 100, 100, 100]


def test_offset_of_progression():
    g = GearedPerPage(GEARED)
    assert [g.offset_of(n) for n in range(1, 7)] == [0, 15, 45, 95, 195, 295]


@pytest.mark.parametrize(
    "total, expected",
    [
        (0, 0),
        (15, 1),
        (16, 2),
        (45, 2),
        (46, 3),
        (95, 3),
        (96, 4),
        (100, 4),
        (195, 4),
        (196, 5),
    ],
)
def test_page_count(total, expected):
    assert GearedPerPage(GEARED).page_count(total) == expected


def test_int_is_fixed_size():
    g = GearedPerPage(20)
    assert g.size_of(1) == 20
    assert g.size_of(9) == 20
    assert g.offset_of(3) == 40
    assert g.page_count(100) == 5


def test_invalid_page_and_sizes():
    g = GearedPerPage(GEARED)
    with pytest.raises(InvalidPage):
        g.size_of(0)
    with pytest.raises(ValueError):
        GearedPerPage([])
    with pytest.raises(ValueError):
        GearedPerPage([10, -1])
