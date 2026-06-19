import typing as t

from .cursor import encode_cursor
from .keyset import keyset_predicate


if t.TYPE_CHECKING:
    from .recordset import Recordset


class Page:
    """A single page of records from a class `Recordset`.

    Records are fetched lazily on first access. One extra row is requested
    (`LIMIT size + 1`) so that :attr:`is_last` is known without a separate
    `COUNT` query — this is what makes cursor paging count-free.
    """

    def __init__(self,
        recordset: "Recordset",
        *,
        number: int,
        cursor_values: list[t.Any] | None = None
    ):
        self.recordset = recordset
        self.number = number
        self._cursor_values = cursor_values
        self._records: list[t.Any] | None = None
        self._has_more: bool | None = None
        self._last_values: list[t.Any] | None = None

    def __iter__(self):
        return iter(self.records)

    def __len__(self):
        return len(self.records)

    def _load(self):
        rs = self.recordset
        size = rs.per_page.size_of(self.number)
        ordered_by = rs.ordered_by
        if ordered_by is not None:
            query = rs.ordered_query()
            if self._cursor_values is not None:
                query = query.where(
                    keyset_predicate(ordered_by, self._cursor_values)
                )
            query = query.limit(size + 1)
        else:
            offset = rs.per_page.offset_of(self.number)
            query = rs.ordered_query().limit(size + 1).offset(offset)

        rows = list(query)
        self._has_more = len(rows) > size
        self._records = rows[:size]
        if ordered_by is not None and self._records:
            last = self._records[-1]
            self._last_values = [
                getattr(last, field.name) for field, _ in ordered_by
            ]

    def _ensure_loaded(self):
        if self._records is None:
            self._load()

    @property
    def records(self) -> list[t.Any]:
        self._ensure_loaded()
        assert self._records is not None
        return self._records

    @property
    def size(self) -> int:
        """Maximum records this page can hold (its geared size)."""
        return self.recordset.per_page.size_of(self.number)

    @property
    def offset(self) -> int:
        """Record offset of this page (offset mode only; 0 under cursor)."""
        if self.recordset.is_cursor:
            return 0
        return self.recordset.per_page.offset_of(self.number)

    @property
    def is_first(self) -> bool:
        if self.recordset.is_cursor:
            return self._cursor_values is None
        return self.number == 1

    @property
    def is_last(self) -> bool:
        self._ensure_loaded()
        return not self._has_more

    @property
    def is_empty(self) -> bool:
        self._ensure_loaded()
        return len(self.records) == 0

    @property
    def is_only(self) -> bool:
        """True when this is the one and only page."""
        return self.is_first and self.is_last

    @property
    def is_before_last(self) -> bool:
        """True when at least one more page follows this one."""
        return not self.is_last

    @property
    def next_param(self):
        """Value for the next page, or `None` when this is the last page.

        Offset mode returns the next page number; cursor mode returns an
        opaque cursor token encoding the next page number plus the keyset.
        """
        self._ensure_loaded()
        if self._has_more is False:
            return None
        if self.recordset.is_cursor:
            assert self._last_values is not None
            return encode_cursor(
                self.number + 1,
                self._last_values,
                secret=self.recordset.cursor_secret,
            )
        return self.number + 1

    @property
    def cache_key(self) -> str:
        """A stable key for this page, suitable as an ETag.

        Carries the page number and the geared sizes (e.g.
        `page/2:15-30-50-100`), but not the keyset values, so it does not
        force the records to load.
        """
        return f"page/{self.number}:{self.recordset.per_page.cache_key}"

