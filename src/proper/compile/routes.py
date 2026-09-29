"""Route matching decided once per router, not once per request.

A router keeps its dynamic routes (the ones with placeholders or a host
constraint) in a list per HTTP method and, until now, matched a request by
trying them one by one: a host check and a path regex per route, in Python,
until one matched. That is O(routes) Python calls per request.

`lower_routes` folds every run of routes without a host constraint into one
regex, an alternation of the routes' own patterns in registration order,
so the whole run is one `re.match` in C. Which route matched comes from the
name of the outer group that closed last; its parameters from groups renamed
per route so they cannot collide.

Most routes start with a literal segment (`/posts/:id`), and two routes
with different first segments can never match the same path, so a run of
those is further split by first segment: a dict lookup picks the one
combined regex that can match. Routes that start with a placeholder, and
routes with a host constraint, stay at their position as their own
segment, so priority is exactly what the registration order says.
"""
import re
import typing as t
from dataclasses import dataclass


if t.TYPE_CHECKING:
    from ..router import Route
    from ..router.router import BaseRouter


RE_GROUP_NAME = re.compile(r"\(\?P([<=])([_a-zA-Z][_a-zA-Z0-9]*)([>)])")

TCaster = t.Callable[[str], t.Any] | None
TFound = tuple["Route", dict] | None


def _rename_groups(pattern: str, prefix: str) -> str:
    """Prefix every named group (and named backreference) of `pattern`."""
    return RE_GROUP_NAME.sub(rf"(?P\1{prefix}\2\3", pattern)


@dataclass(slots=True)
class Combined:
    """A run of dynamic routes without host constraint, as one regex."""

    pattern: re.Pattern
    routes: tuple["Route", ...]
    #: Per route, in the same order: `(param name, group name, caster)`.
    groups: tuple[tuple[tuple[str, str, TCaster], ...], ...]

    def lookup(self, path: str, host: str | None) -> TFound:
        m = self.pattern.match(path)
        if m is None:
            return None
        index = int(m.lastgroup[1:])  # type: ignore[index]
        params = {}
        for name, group, caster in self.groups[index]:
            value = m.group(group)
            params[name] = caster(value) if caster and value is not None else value
        return self.routes[index], params


@dataclass(slots=True)
class Bucketed:
    """Consecutive routes whose path starts with a literal segment, one
    `Combined` per distinct first segment."""

    buckets: dict[str, Combined]

    def lookup(self, path: str, host: str | None) -> TFound:
        end = path.find("/", 1)
        first = path[1:] if end < 0 else path[1:end]
        combined = self.buckets.get(first)
        if combined is None:
            return None
        return combined.lookup(path, host)


@dataclass(slots=True)
class Hosted:
    """One dynamic route with a host constraint, matched as before."""

    route: "Route"

    def lookup(self, path: str, host: str | None) -> TFound:
        route = self.route
        host_params = route.match_host(host)
        if host_params is None:
            return None
        params = route.match(path)
        if params is None:
            return None
        host_params.update(params)
        return route, host_params


TSegment = Combined | Bucketed | Hosted


@dataclass(slots=True)
class RouteTable:
    """The dynamic routes of a router, by method, as segments to try in order."""

    segments: dict[str, tuple[TSegment, ...]]

    def lookup(self, method: str, path: str, host: str | None) -> TFound:
        for segment in self.segments.get(method, ()):
            found = segment.lookup(path, host)
            if found is not None:
                return found
        return None

    def allowed_methods(self, method: str, path: str, host: str | None) -> set[str]:
        """The methods, other than `method`, with a dynamic route for `path`."""
        allowed = set()
        for other, segments in self.segments.items():
            if other == method:
                continue
            for segment in segments:
                if segment.lookup(path, host) is not None:
                    allowed.add(other)
                    break
        return allowed


def combine(routes: "list[Route]") -> Combined:
    """Fold `routes`, none with a host constraint, into one `Combined`."""
    alternatives = []
    groups = []
    for index, route in enumerate(routes):
        prefix = f"r{index}_"
        assert route.path_re
        alternatives.append(
            f"(?P<r{index}>{_rename_groups(route.path_re.pattern, prefix)})"
        )
        casters = route.path_casters
        groups.append(
            tuple(
                (name, prefix + name, casters.get(name))
                for name in route.path_re.groupindex
            )
        )
    return Combined(
        pattern=re.compile("|".join(alternatives)),
        routes=tuple(routes),
        groups=tuple(groups),
    )


def _first_literal_segment(route: "Route") -> str | None:
    """The first segment of the route's path when it has no placeholder."""
    segment = route.path.split("/", 2)[1]
    return None if ":" in segment else segment


def bucket(routes: "list[Route]") -> Bucketed:
    """Split `routes`, all starting with a literal segment and none with a
    host constraint, by that segment."""
    by_segment: dict[str, list[Route]] = {}
    for route in routes:
        first = _first_literal_segment(route)
        assert first is not None
        by_segment.setdefault(first, []).append(route)
    return Bucketed(
        buckets={first: combine(group) for first, group in by_segment.items()}
    )


def _segments(routes: "list[Route]") -> tuple[TSegment, ...]:
    """The routes of one method as segments to try in order."""
    result: list[TSegment] = []
    run: list[Route] = []
    literal = False

    def flush() -> None:
        if run:
            result.append(bucket(run) if literal else combine(run))
            run.clear()

    for route in routes:
        if route.host:
            flush()
            result.append(Hosted(route))
            continue
        is_literal = _first_literal_segment(route) is not None
        if is_literal != literal:
            flush()
            literal = is_literal
        run.append(route)
    flush()
    return tuple(result)


def lower_routes(router: "BaseRouter") -> RouteTable:
    """Build the `RouteTable` of `router` from its dynamic routes."""
    return RouteTable(
        segments={
            method: _segments(routes)
            for method, routes in router._dynamic_routes.items()
        }
    )
