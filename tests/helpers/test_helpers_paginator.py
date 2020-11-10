from proper.helpers import Dot, Paginator, sanitize_page_number


def test_sanitize_page_number():
    assert sanitize_page_number("1") == 1
    assert sanitize_page_number("-1") == 1
    assert sanitize_page_number("0") == 1
    assert sanitize_page_number("3") == 3
    assert sanitize_page_number("asas") == 1
    assert sanitize_page_number(None) == 1


def test_basic_paginator():
    """The paginator is a helper class that can be used with any iterable
    object.
    """
    items = range(198)
    p = Paginator(items, page=1, per_page=10)

    assert p.page == 1
    assert not p.has_prev
    assert p.has_next
    assert p.total == 199
    assert p.num_pages == 20
    assert p.next_num == 2
    assert list(p.pages) == [1, 2, 3, 4, None, 19, 20]


def test_paginator_when_middle_page():
    items = range(1, 198)
    p = Paginator(items, page=10, per_page=10)

    assert list(p.pages) == [1, 2, None, 7, 8, 9, 10, 11, 12, 13, 14, None, 24, 25]


def test_abstract_list_paginator():
    """Yes indeed, the paginator can be used too without anything to actually
    be paginated. How quaint!
    """
    p = Paginator(query=None, page=1, per_page=20, total=490)

    assert p.page == 1
    assert not p.has_prev
    assert p.has_next
    assert p.total == 490
    assert p.num_pages == 25
    assert p.next_num == 2
    assert list(p.pages) == [1, 2, 3, 4, 5, None, 24, 25]

    p.page = 10
    assert list(p.pages) == [1, 2, None, 7, 8, 9, 10, 11, 12, 13, 14, None, 24, 25]


def test_paginator_when_0_items_per_page():
    items = range(1, 491)
    p = Paginator(items, page=1, per_page=0)
    assert p.num_pages == 0


class FakeQuery:
    def __init__(self, items):
        self._items = items
        self._offset = 0
        self._limit = len(items)

    @property
    def items(self):
        return self._items[self._offset:self._offset + self._limit]

    def order_by(self, _order):
        self._order = _order
        return self

    def limit(self, _limit):
        self._limit = _limit
        return self

    def offset(self, _offset):
        self._offset = _offset
        return self

    def count(self):
        return len(self.items)

    def __iter__(self):
        return self.items.__iter__()

def test_paginated_query():
    query = FakeQuery([Dot({"id": i}) for i in range(1, 26)])
    p = Paginator(query, page=2, per_page=5)
    items_in_page = list(p)

    assert items_in_page[0].id == 6
    assert items_in_page[1].id == 7


def test_bool_paginator():
    assert Paginator(range(5))
    assert not Paginator([])
