from proper.concerns.pagination.recordset import Recordset
from .conftest import Post


def _rs(per_page=None):
    query = Post.select().order_by(Post.id)
    return Recordset(query, per_page=per_page or [15, 30, 50, 100])


def test_geared_sizes_and_counts(posts):
    rs = _rs()
    assert rs.records_count == 100
    assert rs.page_count == 4
    assert [len(rs.page(n).records) for n in (1, 2, 3, 4)] == [15, 30, 50, 5]


def test_records_are_contiguous_and_complete(posts):
    rs = _rs()
    ids = []
    for n in (1, 2, 3, 4):
        ids.extend(p.id for p in rs.page(n).records)
    assert ids == list(range(1, 101))


def test_offset_values(posts):
    rs = _rs()
    assert [rs.page(n).offset for n in (1, 2, 3, 4)] == [0, 15, 45, 95]


def test_is_first_last_and_next_param(posts):
    rs = _rs()
    assert rs.page(1).is_first is True
    assert rs.page(1).is_last is False
    assert rs.page(1).next_param == 2
    assert rs.page(3).next_param == 4
    last = rs.page(4)
    assert last.is_last is True
    assert last.next_param is None


def test_empty_recordset(make_posts):
    make_posts(0)
    rs = _rs()
    page = rs.page(1)
    assert rs.records_count == 0
    assert rs.page_count == 0
    assert page.is_empty is True
    assert page.is_last is True
    assert page.next_param is None
