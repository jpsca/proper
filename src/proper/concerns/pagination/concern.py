import typing as t
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ..concern import Concern
from .page import Page
from .recordset import Recordset


class Pagination(Concern):
    """A concern for handling pagination in controllers.

    **Geared page sizes**: instead of a fixed `per_page`, you give a
    progression like `[15, 30, 50, 100]`: page 1 returns 15 records, page 2
    returns 30, page 3 returns 50, and every page from 4 onward returns 100.
    Render the first screen fast, then load bigger batches.

    **Two paging modes**: classic `LIMIT/OFFSET` by page number, or
    count-free **cursor (keyset)** paging when you pass `ordered_by`.
    """

    after = {"do": "_set_paginated_headers"}

    @property
    def etag(self) -> str:
        page = getattr(self, "page", None)
        if page is None or not isinstance(page, Page):
            return super().etag
        return f"{super().etag}-{page.cache_key}".strip("-")

    def paginate_for(
        self,
        query,
        *,
        per_page=None,
        ordered_by=None,
        cursor_secret: str | bytes | None = None,
    ) -> list[t.Any]:
        """Add `self.page` for the given query and pagination parameters."""

        recordset = Recordset(
            query,
            per_page=per_page,
            ordered_by=ordered_by,
            cursor_secret=cursor_secret,
        )
        self.page = recordset.page(self.params.get("page"))
        return self.page.records

    # Private

    def _set_paginated_headers(self) -> None:
        """Set pagination headers on JSON responses.

        Adds `X-Total-Count` with the total number of records and, unless
        this is the last page, a `Link` header pointing at the next page
        (`rel="next"`). Does nothing for non-JSON responses or when the
        action didn't paginate.
        """
        page = getattr(self, "page", None)
        if not isinstance(page, Page):
            return
        if "json" not in (self.response.content_type or ""):
            return

        # `X-Total-Count` needs a COUNT; skip it under cursor paging to keep
        # that mode count-free.
        if not page.recordset.is_cursor:
            self.response.headers["X-Total-Count"] = str(page.recordset.records_count)
        if not page.is_last:
            url = self._next_page_url(page.next_param)
            self.response.headers["Link"] = f'<{url}>; rel="next"'

    def _next_page_url(self, next_param: t.Any) -> str:
        """The current URL with its `page` query param set to `next_param`."""
        parts = urlsplit(self.request.url)
        query = [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key != "page"
        ]
        query.append(("page", str(next_param)))
        return urlunsplit(parts._replace(query=urlencode(query)))
