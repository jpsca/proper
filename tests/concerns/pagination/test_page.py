import pytest

from proper.concerns.pagination.geared_page import GearedPerPage
from proper.concerns.pagination.recordset import Recordset
from proper.errors import InvalidPage
from .conftest import Post


def _rs(per_page=None):
    query = Post.select().order_by(Post.id)
    return Recordset(query, per_page=per_page or [15, 30, 50, 100])


def _cursor_rs(per_page=None):
    return Recordset(
        Post.select(),
        per_page=per_page or [15, 30, 50, 100],
        ordered_by=[(Post.created_at, "desc"), (Post.id, "desc")],
    )


def test_is_only_true_when_a_single_page_holds_everything(posts):
    page = _rs(per_page=[200]).page(1)
    assert page.is_only is True
    assert page.is_first is True
    assert page.is_last is True
    assert page.is_before_last is False


def test_is_only_false_with_multiple_pages(posts):
    assert _rs().page(1).is_only is False


def test_is_before_last(posts):
    rs = _rs()
    assert rs.page(1).is_before_last is True
    # 15 + 30 + 50 = 95, so page 4 is the last page.
    assert rs.page(4).is_before_last is False


def test_iter_and_len_match_records(posts):
    page = _rs().page(2)
    assert list(page) == page.records
    assert len(page) == len(page.records) == 30


def test_size_is_geared(posts):
    rs = _rs()
    assert [rs.page(n).size for n in (1, 2, 3, 4)] == [15, 30, 50, 100]


def test_offset_is_zero_under_cursor(posts):
    assert _cursor_rs().page(None).offset == 0


def test_offset_of_rejects_invalid_page():
    with pytest.raises(InvalidPage):
        GearedPerPage([15, 30]).offset_of(0)
