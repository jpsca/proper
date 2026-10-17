from proper.check import ERROR, Problem
from proper.check.routes import check_views
from proper.check.urls import UrlCall, check_code_urls, check_view_urls, url_problem
from .conftest import extend


def call(name, *keywords, open=False):
    return UrlCall(name=name, keywords=frozenset(keywords), open=open, line=1, col=0)


def test_url_problem(make_shop):
    app = make_shop()
    assert url_problem(app, call("Post.index")) == ""
    assert url_problem(app, call("Post.show", "id")) == ""
    assert url_problem(app, call("Post.show", open=True)) == ""
    assert url_problem(app, call("Post.show")) == "the route `Post.show` (/posts/:id) needs `id`"
    assert url_problem(app, call("Post.shwo")) == (
        "there is no route named `Post.shwo` (did you mean `Post.show`?)"
    )
    assert url_problem(app, call("Nothing.like.it")) == "there is no route named `Nothing.like.it`"


def test_urls_in_the_views(make_shop):
    app = make_shop({
        "shop/views/post/show.jx": """
            {# import "../card.jx" as Card #}
            <h1>Publicación</h1>
            <a href="{{ url_for('Post.index') }}">Índice</a> <a href="{{ url_for('Post.indx') }}">x</a>
            <a href="{{ url_for('Post.show', id=1) }}">{{ url_for('Post.show') }}</a>
            <a href="{{ url_for('Post.show', post) }}">{{ url_for('Post.show', id=post.id) }}</a>
            <a href="{{ url_for('Post.show', **params) }}">{{ url_for(name) }} {{ url_for('/about') }}</a>
            <Card />
        """,
        "shop/views/post/index.jx": """
            {# import "../card.jx" as Card #}
            <Card />
        """,
        "shop/views/card.jx": """
            <p>{{ url_for('Card.show') }}</p>
        """,
    })
    assert check_views(app) == []
    assert check_view_urls(app) == [
        Problem(ERROR, "there is no route named `Card.show`", path="shop/views/card.jx", line=1, col=7),
        Problem(
            ERROR,
            "there is no route named `Post.indx` (did you mean `Post.index`?)",
            path="shop/views/post/show.jx",
            line=3,
            col=62,
        ),
        Problem(
            ERROR,
            "the route `Post.show` (/posts/:id) needs `id`",
            path="shop/views/post/show.jx",
            line=4,
            col=47,
        ),
    ]


def test_urls_of_a_deleted_view(make_shop):
    """A compiled view whose template is gone is not read."""
    app = make_shop({"shop/views/post/old.jx": "{{ url_for('Post.gone') }}\n"})
    check_views(app)
    assert len(check_view_urls(app)) == 1
    (app.views_path / "post" / "old.jx").unlink()
    assert check_view_urls(app) == []


def test_urls_before_the_views_compile(make_shop):
    app = make_shop()
    app.catalog.output = None
    assert check_view_urls(app) == []


def test_urls_in_the_code(make_shop):
    app = make_shop({
        **extend("shop/controllers.py", """

            class DraftController(Controller):
                @router.get("drafts")
                def index(self):
                    self.response.redirect_to("Post.indx", flash="Moved")
                    self.response.redirect_to("/posts")
                    self.response.redirect_to("https://example.com")
                    self.response.redirect_to("Post.show", self.post)
                    url = url_for("Post.show")  # noqa
                    return self.app.url_for("Post.show", id=1, **self.params)
        """),
        "shop/broken.py": "def oops(:\n",
        "shop/latin.py": b"# \xe9\n".decode("latin-1"),
    })
    (app.root_path / "latin.py").write_bytes(b"x = '\xe9'\n")
    assert check_code_urls(app) == [
        Problem(
            ERROR,
            "there is no route named `Post.indx` (did you mean `Post.index`?)",
            path="shop/controllers.py",
            line=23,
            col=9,
        ),
        Problem(
            ERROR,
            "the route `Post.show` (/posts/:id) needs `id`",
            path="shop/controllers.py",
            line=27,
            col=15,
        ),
    ]


def test_urls_in_the_code_skip_the_compiled_views(make_shop):
    app = make_shop({"shop/views/post/old.jx": "{{ url_for('Post.gone') }}\n"})
    app.catalog.output = app.root_path / "views"
    (app.root_path / "views" / "stray.py").write_text("url_for('Post.gone')\n")
    assert check_code_urls(app) == []


def test_urls_in_compiled_modules_without_a_map(make_shop):
    """A module of the output folder that is not a compiled view, and a
    call that the map of its view doesn't place."""
    app = make_shop()
    check_views(app)
    output = app.catalog.output
    (output / "helper.py").write_text("url_for('Post.gone')\n")
    (output / "odd.py").write_text(
        "SOURCES = ()\nLINEMAP = ()\n\n\ndef render(_globals):\n"
        "    return _globals['url_for']('Post.gone')\n"
    )
    [problem] = check_view_urls(app)
    assert problem.message == "there is no route named `Post.gone`"
    assert problem.path.endswith("odd.py")
    assert (problem.line, problem.col) == (6, 0)
