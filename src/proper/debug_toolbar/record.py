"""What the toolbar knows about one request, and where the last ones are kept."""
import threading
import typing as t
from collections import Counter, OrderedDict
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime


PROBLEM_LEVELS = ("WARNING", "ERROR", "CRITICAL")

#: The record of the request being answered, or `None` outside a request
#: (a task, the CLI) and for the requests the toolbar doesn't record.
active: ContextVar["Record | None"] = ContextVar("debug_toolbar.record", default=None)


@dataclass(slots=True)
class Query:
    db: str
    sql: str
    params: str
    ms: float
    error: str = ""
    #: The line of the app that ran the query: `path:line in function`
    origin: str = ""
    #: How many queries of the request have this same SQL
    repeated: int = 1
    #: A query of the cache store (`SqliteCache`), not one the app wrote
    cache: bool = False
    #: The component that was rendering when it ran: `project/index.jx`
    component: str = ""


@dataclass(slots=True)
class CacheCall:
    #: `get`, `set`, `delete`, `increment`, `read_multi`...
    op: str
    key: str
    ms: float
    #: For a read: whether the key was there. `None` for the other calls.
    hit: bool | None = None


@dataclass(slots=True)
class ComponentCall:
    """A component rendered by a view, with the ones it rendered."""

    view: str
    #: With the components it rendered. Not with its content, which is
    #: rendered before it, by the component that uses it.
    ms: float = 0.0
    #: Queries run while it rendered, with those of its components
    queries: int = 0
    #: Calls in a row, with the same parent, shown as one (a loop)
    count: int = 1
    children: list["ComponentCall"] = field(default_factory=list)

    @property
    def self_ms(self) -> float:
        """Without the components it rendered."""
        return max(self.ms - sum(child.ms for child in self.children), 0.0)

    def add(self, child: "ComponentCall") -> None:
        """Add a finished call. One like the last (same component, nothing
        inside) is counted in it: a loop of 200 rows is one line."""
        last = self.children[-1] if self.children else None
        if (
            last is not None
            and last.view == child.view
            and not last.children
            and not child.children
        ):
            last.count += 1
            last.ms += child.ms
            last.queries += child.queries
        else:
            self.children.append(child)

    def rows(self, depth: int = 0) -> t.Iterator[tuple[int, "ComponentCall"]]:
        """This call and those inside it, each with its depth."""
        yield depth, self
        for child in self.children:
            yield from child.rows(depth + 1)


@dataclass(slots=True)
class Render:
    view: str
    ms: float
    #: The arguments of the view: `{name: text}`
    variables: dict[str, str] = field(default_factory=dict)
    #: The view, as the root of the components it rendered
    tree: ComponentCall | None = None

    @property
    def rows(self) -> list[tuple[int, ComponentCall]]:
        return list(self.tree.rows()) if self.tree else []

    @property
    def component_count(self) -> int:
        return sum(call.count for _depth, call in self.rows)


@dataclass(slots=True)
class LogLine:
    #: Milliseconds since the request started
    at: float
    level: str
    logger: str
    message: str


@dataclass(slots=True)
class Record:
    id: str
    started_at: datetime
    method: str = ""
    path: str = ""
    url: str = ""
    status: int = 0
    ms: float = 0.0
    content_type: str = ""
    turbo_frame: str = ""
    error: str = ""

    route_name: str = ""
    route_path: str = ""
    controller: str = ""
    action: str = ""

    #: The request was a prefetch (Turbo asks for a link on hover)
    prefetch: bool = False
    #: Path of the `Location` header of a redirect
    redirect_to: str = ""
    #: ID of the request whose redirect led to this one
    redirected_from: str = ""

    queries: list[Query] = field(default_factory=list)
    cache_calls: list[CacheCall] = field(default_factory=list)
    renders: list[Render] = field(default_factory=list)
    logs: list[LogLine] = field(default_factory=list)
    #: The components being rendered, the innermost last
    rendering: list[ComponentCall] = field(default_factory=list)
    #: `(pipeline step, ms)`
    steps: list[tuple[str, float]] = field(default_factory=list)
    #: `(title, {name: text})`, shown as tables
    request_data: list[tuple[str, dict[str, str]]] = field(default_factory=list)
    response_data: list[tuple[str, dict[str, str]]] = field(default_factory=list)

    @property
    def app_queries(self) -> list[Query]:
        """The queries of the app's databases, without those of the cache."""
        return [query for query in self.queries if not query.cache]

    @property
    def cache_queries(self) -> list[Query]:
        return [query for query in self.queries if query.cache]

    @property
    def sql_ms(self) -> float:
        return sum(query.ms for query in self.queries if not query.cache)

    @property
    def cache_ms(self) -> float:
        return sum(query.ms for query in self.queries if query.cache)

    @property
    def render_ms(self) -> float:
        return sum(render.ms for render in self.renders)

    @property
    def cache_hits(self) -> int:
        return sum(1 for call in self.cache_calls if call.hit is True)

    @property
    def cache_misses(self) -> int:
        return sum(1 for call in self.cache_calls if call.hit is False)

    @property
    def cache_calls_ms(self) -> float:
        return sum(call.ms for call in self.cache_calls)

    @property
    def problems(self) -> int:
        """Log lines that are warnings or worse."""
        return sum(1 for line in self.logs if line.level in PROBLEM_LEVELS)

    @property
    def kind(self) -> str:
        if self.status >= 500:
            return "error"
        if self.status >= 400:
            return "warn"
        if self.status >= 300:
            return "redirect"
        return "ok"

    @property
    def repeated_count(self) -> int:
        """Queries whose SQL is run more than once in the request."""
        return sum(1 for query in self.queries if query.repeated > 1)

    @property
    def target(self) -> str:
        if self.controller:
            return f"{self.controller}.{self.action}"
        return self.route_name

    def count_repeated(self) -> None:
        # The cache reads and writes one key per query: the same SQL many
        # times is how it works, not a query in a loop.
        queries = self.app_queries
        counts = Counter((query.db, query.sql) for query in queries)
        for query in queries:
            query.repeated = counts[query.db, query.sql]


class Store:
    """The records of the last `size` requests, by request ID.

    In memory, so each process has its own: with `PROCESSES` over 1, the
    page of a request is found only when the same process answers.
    """

    def __init__(self, size: int = 50) -> None:
        self.size = size
        self._records: OrderedDict[str, Record] = OrderedDict()
        self._lock = threading.Lock()

    def add(self, record: Record) -> None:
        with self._lock:
            self._records[record.id] = record
            self._records.move_to_end(record.id)
            while len(self._records) > self.size:
                self._records.popitem(last=False)

    def get(self, record_id: str) -> Record | None:
        with self._lock:
            return self._records.get(record_id)

    def latest(self) -> list[Record]:
        """Newest first."""
        with self._lock:
            return list(reversed(self._records.values()))

    def clear(self) -> None:
        with self._lock:
            self._records.clear()

    def __len__(self) -> int:
        return len(self._records)

    def __iter__(self) -> t.Iterator[Record]:
        return iter(self.latest())
