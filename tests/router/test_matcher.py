"""The linear matcher gives the results of `re` without backtracking."""

import random
import re
import time

import pytest

from proper.compile.routes import Combined, Hosted
from proper.errors import MatchNotFound
from proper.router import Route, Router
from proper.router.matcher import (
    ALT,
    INFINITE,
    LIT,
    RUN,
    _custom_elements,
    linear_pattern,
)
from proper.router.route import MAX_HOST_LENGTH, _compile_pattern


class H:
    def a(self): ...


# The formats the matcher reads: the built-in ones and custom ones.
FORMATS = [
    "",
    "",
    "<path>",
    "<int>",
    "<float>",
    "<[a-z]+>",
    "<[a-z.]+>",
    "<[^.]+>",
    r"<\d{2}>",
    "<[0-9]{1,3}>",
    "<a|ab|b>",
    "<en|es>",
    "<[a-z]*>",
    "<.?>",
    "<-+>",
    r"<\w+>",
    "<[^/]{2,}>",
    r"<\.+>",
    "<x>",
    r"<[a\]]{,2}>",
]
LITERAL_CHARS = ["/", ".", "-", "a", "b", "x", "1", "é", "\n"]
SUBJECT_CHARS = ["/", ".", "-", "a", "b", "x", "1", "2", "é", "\n", "e", "]"]


def _literal(rng: random.Random) -> str:
    text = "".join(rng.choice(LITERAL_CHARS) for _ in range(rng.choice([0, 1, 1, 2])))
    # Text right after a placeholder must not extend its name or format.
    return "-" + text if text[:1].isalnum() else text


def _pattern(rng: random.Random) -> str:
    out = _literal(rng)
    for name in "abcd"[: rng.choice([2, 2, 3, 3, 4])]:
        out += f":{name}{rng.choice(FORMATS)}{_literal(rng)}"
    return out


def _subject(rng: random.Random, pattern: str) -> str:
    if rng.random() < 0.5:
        size = rng.choice([0, 1, 2, 4, 8, 12])
        return "".join(rng.choice(SUBJECT_CHARS) for _ in range(size))

    def value(m):
        size = rng.choice([1, 1, 2, 3])
        return "".join(rng.choice(SUBJECT_CHARS) for _ in range(size))

    return re.sub(r":[a-d](<[^>]+>)?", value, pattern)


@pytest.mark.parametrize("anchor", [r"/?$", r"$"])
def test_same_results_as_re(anchor):
    rng = random.Random(20261008)
    linear_patterns = matched = 0
    for _ in range(3000):
        pattern = _pattern(rng)
        compiled, *_, linear = _compile_pattern(pattern, anchor_suffix=anchor)
        if linear is None:
            continue
        linear_patterns += 1
        for _ in range(12):
            subject = _subject(rng, pattern)
            m = compiled.match(subject)
            expected = None if m is None else m.groupdict()
            assert linear.match_linear(subject) == expected, (pattern, subject)
            assert linear.match(subject) == expected, (pattern, subject)
            matched += expected is not None
    # Most generated patterns use the matcher, and many subjects match.
    assert linear_patterns > 1500
    assert matched > 600


@pytest.mark.parametrize(
    "path, subject",
    [
        ("/x/:a-:b-:c.html", "/x/" + "-" * 64_000 + "x"),
        ("/f/:a<path>/:b<path>", "/f/" + "/" * 64_000 + "\nx"),
        ("/f/:a<[a-z.]+>.:b<[a-z.]+>.:c.html", "/f/" + "." * 64_000),
    ],
)
def test_long_path_that_does_not_match_is_quick(path, subject):
    # With `re`, these took longer the more placeholders: a few seconds at
    # 2 000 characters for the first one, and hours at 64 000.
    router = Router()
    router.add_route(Route("GET", path, to=H.a))
    start = time.perf_counter()
    with pytest.raises(MatchNotFound):
        router.match("GET", subject)
    assert time.perf_counter() - start < 2


def test_long_path_that_matches():
    router = Router()
    router.add_route(Route("GET", "/x/:a-:b-:c.html", to=H.a))
    subject = "/x/" + "-" * 64_000 + "x.html"
    _, params = router.match("GET", subject)
    m = re.match(r"/x/(?P<a>[^\/]+)-(?P<b>[^\/]+)-(?P<c>[^\/]+)\.html/?$", subject)
    assert params == m.groupdict()


def test_short_subjects_use_re_and_long_ones_do_not():
    route = Route("GET", "/x/:a-:b-:c.html")
    linear = route._path_linear
    size = linear.re_max_size
    assert size > 10
    short = "/x/" + "-" * (size - 4) + "x"
    long = "/x/" + "-" * (size - 3) + "x"
    assert len(short) == size
    assert linear.match(short) is None
    assert linear.match(long) is None

    regex = linear.regex

    class Counting:
        calls = 0

        def match(self, subject):
            Counting.calls += 1
            return regex.match(subject)

    linear.regex = Counting()
    assert linear.match(short) is None
    assert linear.match(long) is None
    assert Counting.calls == 1


def test_re_max_size_shrinks_with_the_choices():
    sizes = [
        Route("GET", pattern)._path_linear.re_max_size
        for pattern in ("/:a-:b", "/:a-:b-:c", "/:a-:b-:c-:d", "/:a-:b-:c-:d-:e")
    ]
    assert sizes == sorted(sizes, reverse=True)
    assert sizes[-1] < sizes[0]


def test_host_linear_matcher_is_quick_without_the_length_limit():
    route = Route("GET", "/h", host=":a.:b.:c.example.com")
    start = time.perf_counter()
    assert route._host_linear.match_linear("." * 64_000 + "x") is None
    assert time.perf_counter() - start < 2


def test_a_host_longer_than_the_limit_matches_no_host_route():
    route = Route("GET", "/h", host=":sub.example.com")
    name = "a" * (MAX_HOST_LENGTH - len(".example.com"))
    assert route.match_host(f"{name}.example.com") == {"sub": name}
    assert route.match_host(f"{name}a.example.com") is None


def test_a_host_longer_than_the_limit_is_a_404_for_host_routes():
    router = Router()
    router.add_route(Route("GET", "/h", to=H.a, host=":sub.example.com"))
    with pytest.raises(MatchNotFound):
        router.match("GET", "/h", "a" * 300 + ".example.com")


@pytest.mark.parametrize(
    "pattern",
    [
        "/posts/:id/edit",
        "/posts/:id/comments/:cid",
        "/:year<int>-:month<int>-:day<int>",
        r"/:year<\d{4}>:slug",
        "/:lang<en|es>/:a/:b.html",
        "/docs/:page<path>",
        "/a/:x/:y.html",
        "/:a",
        "/static",
    ],
)
def test_patterns_re_cannot_backtrack_on_use_re(pattern):
    *_, linear = _compile_pattern(pattern, anchor_suffix=r"/?$")
    assert linear is None


@pytest.mark.parametrize(
    "pattern",
    [
        "/x/:a-:b-:c.html",
        "/f/:a<path>/:b",
        "/:a<int>:b",
        "/:a<[a-z]{1,3}>:b",
        "/:a<ab|a>:b<[a-z]+>",
        ":a.:b.example.com",
        "/:a<float>1:b",
    ],
)
def test_patterns_re_can_backtrack_on_use_the_linear_matcher(pattern):
    *_, linear = _compile_pattern(pattern, anchor_suffix=r"/?$")
    assert linear is not None


@pytest.mark.parametrize(
    "pattern", ["/:a<(?:a|b)+>.:b.:c", "/:a<[a-z]+?>.:b.:c", "/:a.:b<x{,}>.:c"]
)
def test_patterns_with_other_custom_formats_use_re(pattern):
    *_, linear = _compile_pattern(pattern, anchor_suffix=r"/?$")
    assert linear is None


@pytest.mark.parametrize(
    "fmt, expected",
    [
        ("[a-z]+", ((RUN, "[a-z]", 1, INFINITE),)),
        ("[^.]*", ((RUN, "[^.]", 0, INFINITE),)),
        (r"\d?", ((RUN, r"\d", 0, 1),)),
        (r"\d{4}", ((RUN, r"\d", 4, 4),)),
        (r"\w{2,}", ((RUN, r"\w", 2, INFINITE),)),
        (".{,3}", ((RUN, ".", 0, 3),)),
        ("x{1,63}", ((RUN, "x", 1, 63),)),
        (r"\.+", ((RUN, r"\.", 1, INFINITE),)),
        ("en|es|pt", ((ALT, ("en", "es", "pt")),)),
        (r"a\.b|c", ((ALT, ("a.b", "c")),)),
        ("x{}", None),
        ("x{,}", None),
        ("(a|b)+", None),
        ("[a-z]+?", None),
        ("[]a]+", None),
        ("a|", None),
        ("é|e", None),
    ],
)
def test_custom_elements(fmt, expected):
    assert _custom_elements(fmt) == expected


def test_linear_pattern_elements():
    compiled, _, _, _, pieces, linear = _compile_pattern(
        "/:a-:b<float>.html", anchor_suffix=r"/?$"
    )
    assert pieces == [("/", "a"), ("-", "b"), (".html", None)]
    assert linear_pattern(pieces, {"a": None, "b": "float"}, r"/?$", compiled)
    assert linear.elements == (
        (LIT, "/"),
        (RUN, r"[^\/]", 1, INFINITE),
        (LIT, "-"),
        (RUN, "[0-9]", 1, INFINITE),
        (LIT, "."),
        (RUN, "[0-9]", 1, INFINITE),
        (LIT, ".html"),
    )
    assert linear.groups == (("a", 1, 2), ("b", 3, 6))
    assert linear.match("/x-y-1.5.html") == {"a": "x-y", "b": "1.5"}
    assert linear.match_linear("/x-y-1.5.html") == {"a": "x-y", "b": "1.5"}


def test_routes_matched_without_re_are_not_combined():
    router = Router()
    router.add_route(Route("GET", "/a/:x", to=H.a))
    router.add_route(Route("GET", "/b/:x-:y", to=H.a))
    router.add_route(Route("GET", "/c/:x", to=H.a))
    segments = router.lower().segments["GET"]
    assert [type(segment) for segment in segments][1] is Hosted
    assert Combined not in [type(segments[1])]
    # Order is kept: the first route that matches wins.
    route, params = router.match("GET", "/b/1-2")
    assert route.path == "/b/:x-:y"
    assert params == {"x": "1", "y": "2"}


def test_a_route_matched_without_re_refuses_dot_segments_and_casts():
    route = Route("GET", "/f/:a<int>:b/:c", to=H.a)
    assert route.path_backtracks
    assert route.match("/f/12x/..") is None
    assert route.match("/f/12x/y") == {"a": 12, "b": "x", "c": "y"}


def test_a_host_matched_without_re():
    route = Route("GET", "/", host=":a.:b<int>.example.com")
    assert route._host_linear is not None
    assert route.match_host("x.y.12.example.com") == {"a": "x.y", "b": 12}
    assert route.match_host("x.y.example.com") is None
