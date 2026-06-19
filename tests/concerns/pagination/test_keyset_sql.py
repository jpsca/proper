import pytest

from proper.concerns.pagination.keyset import keyset_predicate
from .conftest import Post


def _ordered(ordered_by):
    exprs = [f.desc() if d == "desc" else f.asc() for f, d in ordered_by]
    return list(Post.select().order_by(*exprs))


@pytest.mark.parametrize(
    "ordered_by",
    [
        [(Post.created_at, "asc"), (Post.id, "asc")],
        [(Post.created_at, "desc"), (Post.id, "desc")],
        [(Post.created_at, "asc"), (Post.id, "desc")],
        [(Post.id, "asc")],
    ],
)
@pytest.mark.parametrize("pivot_index", [0, 17, 50, 98])
def test_predicate_returns_rows_strictly_after_pivot(posts, ordered_by, pivot_index):
    rows = _ordered(ordered_by)
    pivot = rows[pivot_index]
    values = [getattr(pivot, f.name) for f, _ in ordered_by]

    predicate = keyset_predicate(ordered_by, values)
    exprs = [f.desc() if d == "desc" else f.asc() for f, d in ordered_by]
    got = [p.id for p in Post.select().where(predicate).order_by(*exprs)]

    expected = [p.id for p in rows[pivot_index + 1 :]]
    assert got == expected


def test_predicate_rejects_a_length_mismatch():
    with pytest.raises(ValueError):
        keyset_predicate([(Post.id, "asc")], [1, 2])
