"""A task enqueued while a request is answered logs with that request's ID."""
import structlog

from proper import App, Controller
from proper.router import Route
from proper.test_client import TestClient
from proper.tools.queue import REQUEST_ID_KWARG


SEEN: list = []
TASKS: dict = {}


class Tasks(Controller):
    def index(self):
        TASKS["remember"]("one")
        return self.render(text="ok")

    def chain(self):
        remember = TASKS["remember"]
        TASKS["app"].queue.enqueue(remember.s("first").then(remember, "second"))
        return self.render(text="ok")

    def retry(self):
        TASKS["fail_once"]()
        return self.render(text="ok")


def make_app(immediate=False):
    app = App(
        "proper",
        {
            "SECRET_KEYS": ["*" * 50],
            "QUEUE": {"type": "huey.MemoryHuey", "immediate": immediate},
        },
    )

    @app.queue.task()
    def remember(*values, **kwargs):
        """A task after another gets the result of that one last."""
        SEEN.append(
            (values, kwargs, structlog.contextvars.get_contextvars().get("request_id"))
        )
        return values[0]

    @app.queue.task(retries=1)
    def fail_once(**kwargs):
        if not SEEN:
            SEEN.append("failed")
            raise ValueError("first try")
        SEEN.append(structlog.contextvars.get_contextvars().get("request_id"))

    TASKS.update(app=app, remember=remember, fail_once=fail_once)
    app.router.add_route(Route("GET", "/", to=Tasks.index))
    app.router.add_route(Route("GET", "/chain", to=Tasks.chain))
    app.router.add_route(Route("GET", "/retry", to=Tasks.retry))
    SEEN.clear()
    return app, remember


def run_the_queue(app):
    """What the consumer does: take each task out of the storage and run it,
    outside of any request."""
    while (task := app.queue.dequeue()) is not None:
        app.queue.execute(task)


def test_the_task_runs_with_the_id_of_the_request():
    app, _ = make_app()
    TestClient(app).get("/", headers={"x-request-id": "abc-123"})

    run_the_queue(app)

    assert SEEN == [(("one",), {}, "abc-123")]
    assert structlog.contextvars.get_contextvars().get("request_id") is None


def test_chained_tasks_too():
    app, _ = make_app()
    TestClient(app).get("/chain", headers={"x-request-id": "abc-123"})

    run_the_queue(app)

    assert SEEN == [
        (("first",), {}, "abc-123"),
        (("second", "first"), {}, "abc-123"),
    ]


def test_a_retry_keeps_the_id():
    app, _ = make_app()
    TestClient(app).get("/retry", headers={"x-request-id": "abc-123"})

    run_the_queue(app)

    assert SEEN == ["failed", "abc-123"]


def test_immediate_mode_keeps_the_id_of_the_request():
    app, _ = make_app(immediate=True)
    TestClient(app).get("/", headers={"x-request-id": "abc-123"})
    assert SEEN == [(("one",), {}, "abc-123")]


def test_outside_a_request_there_is_no_id():
    app, remember = make_app()
    remember("alone")

    task = app.queue.dequeue()
    assert REQUEST_ID_KWARG not in task.kwargs
    app.queue.execute(task)

    assert SEEN == [(("alone",), {}, None)]
