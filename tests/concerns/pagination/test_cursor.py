import pytest

from proper.concerns.pagination.recordset import Recordset
from proper.errors import InvalidOrdering
from .conftest import Post


def _walk(rs):
    """Walk every page via next_param, returning (ids, page_sizes)."""
    ids, sizes = [], []
    page = rs.page(None)
    while True:
        sizes.append(len(page.records))
        ids.extend(p.id for p in page.records)
        token = page.next_param
        if token is None:
            break
        page = rs.page(token)
    return ids, sizes


def test_cursor_walk_matches_full_order_asc(posts):
    ordered_by = [(Post.created_at, "asc"), (Post.id, "asc")]
    rs = Recordset(Post.select(), per_page=[15, 30, 50, 100], ordered_by=ordered_by)
    expected = [p.id for p in Post.select().order_by(Post.created_at, Post.id)]
    ids, sizes = _walk(rs)
    assert ids == expected
    assert sizes == [15, 30, 50, 5]  # geared sizes work under cursor too


def test_cursor_walk_matches_full_order_mixed_directions(posts):
    ordered_by = [(Post.created_at, "desc"), (Post.id, "desc")]
    rs = Recordset(Post.select(), per_page=20, ordered_by=ordered_by)
    expected = [
        p.id
        for p in Post.select().order_by(Post.created_at.desc(), Post.id.desc())
    ]
    ids, _ = _walk(rs)
    assert ids == expected


def test_cursor_no_overlap_or_gap(posts):
    ordered_by = [(Post.created_at, "asc"), (Post.id, "asc")]
    rs = Recordset(Post.select(), per_page=[15, 30, 50, 100], ordered_by=ordered_by)
    ids, _ = _walk(rs)
    assert len(ids) == len(set(ids)) == 100


def test_first_and_last_flags(posts):
    rs = Recordset(
        Post.select(), per_page=[40, 100], ordered_by=[(Post.id, "asc")]
    )
    first = rs.page(None)
    assert first.is_first is True
    assert first.is_last is False
    second = rs.page(first.next_param)
    assert second.is_first is False
    assert second.is_last is True
    assert second.next_param is None


def test_requires_unique_tie_breaker(posts):
    with pytest.raises(InvalidOrdering):
        Recordset(Post.select(), ordered_by=[(Post.created_at, "asc")])
