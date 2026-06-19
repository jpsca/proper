import pytest

from proper.concerns.pagination.geared_page import GearedPerPage
from proper.concerns.pagination.recordset import Recordset, normalize_ordering
from proper.errors import InvalidOrdering
from .conftest import Post


class TestNormalizeOrdering:
    def test_accepts_a_dict_preserving_order(self):
        result = normalize_ordering({Post.created_at: "desc", Post.id: "asc"})
        assert result == [(Post.created_at, "desc"), (Post.id, "asc")]

    def test_bare_field_defaults_to_ascending(self):
        assert normalize_ordering([Post.id]) == [(Post.id, "asc")]

    def test_rejects_an_invalid_direction(self):
        with pytest.raises(InvalidOrdering):
            normalize_ordering([(Post.id, "sideways")])

    def test_rejects_an_empty_ordering(self):
        with pytest.raises(InvalidOrdering):
            normalize_ordering([])


class TestRecordset:
    def test_reuses_a_geared_per_page_instance(self):
        per_page = GearedPerPage([10, 20])
        rs = Recordset(Post.select(), per_page=per_page)
        assert rs.per_page is per_page

    def test_str_cursor_secret_is_encoded_to_bytes(self):
        rs = Recordset(Post.select(), cursor_secret="sekret")
        assert rs.cursor_secret == b"sekret"

    def test_bytes_cursor_secret_is_kept_as_is(self):
        rs = Recordset(Post.select(), cursor_secret=b"sekret")
        assert rs.cursor_secret == b"sekret"

    def test_invalid_cursor_falls_back_to_the_first_page(self):
        rs = Recordset(Post.select(), ordered_by=[(Post.id, "asc")])
        page = rs.page("not-a-valid-cursor")
        assert page.number == 1
        assert page.is_first is True

    def test_invalid_page_number_falls_back_to_the_first_page(self):
        rs = Recordset(Post.select())
        assert rs.page("abc").number == 1
