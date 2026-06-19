# Pagination

A port of Basecamp's [`geared_pagination`](https://github.com/basecamp/geared_pagination)
gem to Python, for [Peewee](http://docs.peewee-orm.com/).

Two ideas:

- **Geared page sizes** — instead of a fixed `per_page`, you give a
  progression like `[15, 30, 50, 100]`: page 1 returns 15 records, page 2
  returns 30, page 3 returns 50, and every page from 4 onward returns 100.
  Render the first screen fast, then load bigger batches.
- **Two paging modes** — classic `LIMIT/OFFSET` by page number, or
  count-free **cursor (keyset)** paging when you pass `ordered_by`.

## In a controller

The `Pagination` concern is the entry point. Mix it into a controller and call
`paginate_for` from an action: it reads the `page` query param, sets `self.page`,
and returns the records for the current page.

```python
from proper.concerns import Pagination


class PostsController(Pagination, Controller):
    def index(self):
        self.posts = self.paginate_for(
            Post.select().order_by(Post.id),
            per_page=[15, 30, 50, 100],
        )
        # `self.page` is a `Page`: self.page.number, self.page.is_last,
        # self.page.next_param, ...
```

On JSON responses the concern also sets `X-Total-Count` and a `Link` header with
`rel="next"` (omitted on the last page), and exposes `self.page.cache_key` as the
controller `etag`.

The sections below describe the underlying `Recordset`/`Page` objects that
`paginate_for` builds for you.

## Offset pagination

```python
from .recordset import Recordset

query = Post.select().order_by(Post.id)
recordset = Recordset(query, per_page=[15, 30, 50, 100])

page = recordset.page(2)
page.records            # the 30 records of page 2
page.number             # 2
page.is_last            # False
page.next_param         # 3  (or None on the last page)
page.recordset.page_count    # total pages
page.recordset.records_count # total records
```

## Cursor (keyset) pagination

Pass `ordered_by` to switch into cursor mode. The last column must be unique
(typically the primary key) so the order is total and pages never skip or
repeat a row. Page sizes stay geared — the page number rides inside the cursor.

```python
recordset = Recordset(
    Post.select(),
    per_page=[15, 30, 50, 100],
    ordered_by=[(Post.created_at, "desc"), (Post.id, "desc")],
    cursor_secret="..."  # optional
)

page = recordset.page(None)   # first page
page.records
token = page.next_param         # opaque cursor string, or None at the end

page = recordset.page(token)  # next page
```

`ordered_by` also accepts a dict (insertion order preserved):
`{Post.created_at: "desc", Post.id: "desc"}`.

Cursors are count-free: each page fetches `size + 1` rows to learn whether a
next page exists, so no `COUNT(*)` is needed to walk a list.

When `cursor_secret` is set, cursors are signed and tamper-detected on decode.


## API

```python
Recordset(query, *, per_page=None, ordered_by=None, cursor_secret=None)
  .page(param)   # `Page` for `param`: a page number (offset mode),
                 # or a cursor token / None (cursor mode)
  .records_count
  .page_count
  .is_cursor
```

```python
Page(recordset, *, number, cursor_values=None)
  # iterable and `len()`-able (yields / counts its records)
  .records
  .number
  .size
  .offset
  .is_first
  .is_last
  .is_empty
  .is_only
  .is_before_last
  .next_param    # next page number / cursor token, or None on the last page
  .cache_key     # stable key for an ETag or fragment cache
```

```python
GearedPerPage(sizes)
  .size_of(n)
  .offset_of(n)
  .page_count(total)
  .cache_key
```

```python
encode_cursor(number, values, secret=None)
decode_cursor(token, secret=None)
# plus the error types: PaginationError, InvalidPage, InvalidCursor, InvalidOrdering.
```
