"""`Route.format` gives what it gave before it was prepared once per route:
thousands of generated routes and values, the errors included. `reference`
is `Route.format` as it was written before."""
import random
from urllib.parse import quote, urlencode

import pytest

from proper.errors import BadRoutePlaceholder, MissingRouteParameter
from proper.router.route import PATH_SAFE, Route, _build, _dot_segment_placeholder


def reference(route, **kw):
    params = {}
    for name, rx in route._path_placeholder_re.items():
        value = kw.get(name)
        if value is None:
            raise MissingRouteParameter(name, route.path)
        value = str(value)
        if not rx.fullmatch(value):
            raise BadRoutePlaceholder(name, route.path, rx.pattern)
        params[name] = value
    values = {name: quote(value, safe=PATH_SAFE) for name, value in params.items()}
    name = _dot_segment_placeholder(route._path_pieces, values)
    if name is not None:
        raise BadRoutePlaceholder(
            name,
            route.path,
            route._path_placeholder_re[name].pattern,
            reason="would make a `.` or `..` segment, which clients remove",
        )
    url = _build(route._path_pieces, values) or "/"
    query = {k: v for k, v in kw.items() if k not in params}
    if query:
        url = url + "?" + urlencode(query)
    return url


def outcome(fn, *args, **kw):
    try:
        return ("ok", fn(*args, **kw))
    except (BadRoutePlaceholder, MissingRouteParameter) as error:
        return (type(error).__name__, str(error))


LITERALS = ["", "/", "posts/", "a b/", "ñ/", "50%/", "x.y/", "./", "files/", "-", "~", "@:"]
FORMATS = ["", "<int>", "<path>", "<float>", "<[a-z]+>", "<[a-z]*>", "<.*>"]
VALUES = [
    0, 7, 42, -1, True, False, 3.5, "3", "42abc", "", "a", "a b", "ñandú", "a/b", ".", "..",
    "a/../b", "./x", "x.", "%", "50%", "a?b", "a#b", "~_-.", ":@!$&'()*+,;=", "日本", "\n",
    None, 1.0, "1.5",
]


def random_route(rnd):
    path = ""
    names = []
    for i in range(rnd.randrange(0, 4)):
        name = f"p{i}"
        path += rnd.choice(LITERALS) + f":{name}" + rnd.choice(FORMATS)
        names.append(name)
    path += rnd.choice(["", "/", "/edit", ".json", "/x y"])
    return Route("GET", path, to=lambda: None), names


@pytest.mark.parametrize("seed", range(6))
def test_generated_routes(seed):
    rnd = random.Random(seed)
    for _ in range(3000):
        route, names = random_route(rnd)
        kw = {}
        for name in names:
            if rnd.random() < 0.95:
                kw[name] = rnd.choice(VALUES)
        for extra in range(rnd.randrange(0, 3)):
            kw[f"q{extra}"] = rnd.choice(VALUES)
        assert outcome(route.format, **kw) == outcome(reference, route, **kw), (route.path, kw)
