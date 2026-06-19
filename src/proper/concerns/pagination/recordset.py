import typing as t
from collections.abc import Sequence

from ...errors import InvalidCursor, InvalidOrdering
from ...helpers import logger
from .cursor import decode_cursor
from .geared_page import GearedPerPage
from .page import Page


if t.TYPE_CHECKING:
    from peewee import SelectQuery


DEFAULT_PER_PAGE = (15, 30, 50, 100)

TOrdering = Sequence[tuple[t.Any, str]] | dict[t.Any, str] | Sequence[t.Any]


def normalize_ordering(ordered_by: TOrdering) -> list[tuple]:
    """Normalize `ordered_by` into a list of `(field, "asc"|"desc")`.

    Accepts:
    - a dict `{Model.created_at: "desc", Model.id: "desc"}` (insertion order is preserved),
    - a sequence of `(field, direction)` pairs, or
    - a sequence of bare fields (treated as ascending).

    """
    if isinstance(ordered_by, dict):
        items = list(ordered_by.items())
    else:
        items = list(ordered_by)

    result = []
    for item in items:
        if isinstance(item, (tuple, list)):
            field, direction = item
        else:
            field, direction = item, "asc"
        direction = str(direction).lower()
        if direction not in ("asc", "desc"):
            raise InvalidOrdering(
                f"ordering direction must be 'asc' or 'desc', got {direction!r}"
            )
        result.append((field, direction))
    if not result:
        raise InvalidOrdering("ordered_by must not be empty")
    return result


class Recordset:
    """Wraps a Peewee query and produces :class:`Page` objects.

    Passing `ordered_by` switches the recordset into cursor (keyset) mode;
    otherwise it paginates by `LIMIT/OFFSET`.
    """

    def __init__(
        self,
        query: "SelectQuery",
        *,
        per_page: int | Sequence[int] | GearedPerPage | None = None,
        ordered_by: TOrdering | None = None,
        cursor_secret: str | bytes | None = None,
    ):
        self.query = query
        if isinstance(per_page, GearedPerPage):
            self.per_page = per_page
        else:
            self.per_page = GearedPerPage(
                per_page if per_page is not None else DEFAULT_PER_PAGE
            )
        self.ordered_by = normalize_ordering(ordered_by) if ordered_by else None
        self._validate_ordering()
        self._records_count: int | None = None

        if cursor_secret is not None:
            if isinstance(cursor_secret, str):
                cursor_secret = cursor_secret.encode("utf-8")
        self.cursor_secret = cursor_secret

    @property
    def is_cursor(self) -> bool:
        return self.ordered_by is not None

    def _validate_ordering(self):
        if not self.ordered_by:
            return

        # The final tie-breaker column must be unique so the order is total
        # and the keyset never skips or repeats rows.
        last_field, _ = self.ordered_by[-1]
        unique = getattr(last_field, "unique", False) or getattr(
            last_field, "primary_key", False
        )
        if not unique:
            raise InvalidOrdering(
                "the last column in ordered_by must be unique (e.g. the primary "
                "key) so cursor paging is deterministic; append the id column"
            )

    def ordered_query(self):
        if not self.ordered_by:
            return self.query
        exprs = [
            field.desc() if direction == "desc" else field.asc()
            for field, direction in self.ordered_by
        ]
        return self.query.order_by(*exprs)

    @property
    def records_count(self) -> int:
        if self._records_count is None:
            # peewee binds `count()`'s database via the @database_required
            # decorator, which the type checker can't see through.
            self._records_count = self.query.count()  # type: ignore
        return self._records_count

    @property
    def page_count(self) -> int:
        return self.per_page.page_count(self.records_count)

    def page(self, param: int | str = "1") -> Page:
        if self.is_cursor:
            if param:
                try:
                    number, values = decode_cursor(str(param), secret=self.cursor_secret)
                except InvalidCursor as e:
                    logger.warning("invalid cursor: %s", e)
                    number, values = 1, None
            else:
                number, values = 1, None
            return Page(self, number=number, cursor_values=values)

        try:
            number = max(int(param), 1)
        except (TypeError, ValueError):
            logger.warning("invalid page number: %s", param)
            number = 1
        return Page(self, number=number)
