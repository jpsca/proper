from proper import Request, Response
from proper.concerns import CurrentLocale, Pagination
from proper.controller import Controller
from proper.helpers.asgi import make_test_scope
from .conftest import Post


def _make(cls, app, **scope_kw):
    scope = make_test_scope(**scope_kw)
    scope["app"] = app
    request = Request(scope)
    response = Response(scope)
    return cls(request, response)


def _dispatch(cls, app, action="index", **scope_kw):
    co = _make(cls, app, **scope_kw)
    co.request.matched_action = action
    co._dispatch(action)
    return co


PER_PAGE = [15, 30, 50, 100]


class OffsetJsonCtrl(Pagination, Controller):
    def index(self):
        self.response.content_type = "application/json"
        self.paginate_for(Post.select().order_by(Post.id), per_page=PER_PAGE)
        return "[]"


class OffsetHtmlCtrl(Pagination, Controller):
    def index(self):
        self.paginate_for(Post.select().order_by(Post.id), per_page=PER_PAGE)
        return "<html></html>"


class CursorJsonCtrl(Pagination, Controller):
    def index(self):
        self.response.content_type = "application/json"
        self.paginate_for(
            Post.select(),
            ordered_by=[(Post.created_at, "desc"), (Post.id, "desc")],
            per_page=PER_PAGE,
        )
        return "[]"


class NoPaginateCtrl(Pagination, Controller):
    def index(self):
        self.response.content_type = "application/json"
        return "[]"


class ComposedCtrl(Pagination, CurrentLocale, Controller):
    def index(self):
        self.paginate_for(Post.select().order_by(Post.id), per_page=PER_PAGE)
        return "[]"


class TestSetPaginatedHeaders:
    def test_offset_first_page_sets_count_and_link(self, app, posts):
        co = _dispatch(OffsetJsonCtrl, app, url="/posts?page=1")
        assert co.response.headers.get("X-Total-Count") == "100"
        assert co.response.headers.get("Link") == '</posts?page=2>; rel="next"'

    def test_offset_last_page_has_count_but_no_link(self, app, posts):
        # 15 + 30 + 50 = 95, so page 4 holds the last 5 records.
        co = _dispatch(OffsetJsonCtrl, app, url="/posts?page=4")
        assert co.response.headers.get("X-Total-Count") == "100"
        assert "Link" not in co.response.headers

    def test_link_preserves_other_query_params(self, app, posts):
        co = _dispatch(OffsetJsonCtrl, app, url="/posts?status=open&page=1")
        link = co.response.headers.get("Link")
        assert "status=open" in link
        assert "page=2" in link

    def test_html_response_sets_no_headers(self, app, posts):
        co = _dispatch(OffsetHtmlCtrl, app, url="/posts?page=1")
        assert "X-Total-Count" not in co.response.headers
        assert "Link" not in co.response.headers

    def test_no_pagination_sets_no_headers(self, app, posts):
        co = _dispatch(NoPaginateCtrl, app, url="/posts")
        assert "X-Total-Count" not in co.response.headers
        assert "Link" not in co.response.headers

    def test_cursor_skips_count_but_sets_link(self, app, posts):
        co = _dispatch(CursorJsonCtrl, app, url="/posts")
        # Cursor paging is count-free: no COUNT, hence no X-Total-Count.
        assert "X-Total-Count" not in co.response.headers
        link = co.response.headers.get("Link")
        assert 'rel="next"' in link
        assert "page=" in link


class TestPaginationEtag:
    def test_etag_is_empty_without_a_page(self, app):
        co = _make(OffsetJsonCtrl, app)
        assert co.etag == ""

    def test_etag_carries_the_page_cache_key(self, app, posts):
        co = _dispatch(OffsetJsonCtrl, app, url="/posts?page=2")
        assert co.etag == "page/2:15-30-50-100"

    def test_etag_composes_with_other_concerns(self, app, posts):
        co = _dispatch(ComposedCtrl, app, url="/posts?page=1&locale=es")
        assert co.etag == "es-page/1:15-30-50-100"
