"""Proper's structlog logger, and the handler that writes the logs of every
logger with the ID of the request."""
import json
import logging

import pytest

from proper import App, Controller
from proper.errors import ConfigError
from proper.helpers import logger, logs
from proper.helpers.logs import _console_renderer, setup_logging
from proper.router import Route
from proper.test_client import TestClient


class Logs(Controller):
    def index(self):
        logger.info("hello %s", "world", color="blue")
        logging.getLogger("peewee").warning("a query")
        try:
            {}["password"] = 1 / 0
        except ZeroDivisionError:
            logger.exception("boom")
        return self.render(text="ok")


def make_app(**config):
    app = App("proper", {"SECRET_KEYS": ["*" * 50], **config})
    app.router.add_route(Route("GET", "/", to=Logs.index))
    return app


def lines(capsys):
    return capsys.readouterr().err.strip().splitlines()


@pytest.fixture(autouse=True)
def _restore_handler():
    yield
    setup_logging("off")


class TestTheLogger:
    def test_formats_the_arguments_and_keeps_the_extra_fields(self, caplog):
        logger.setLevel(logging.DEBUG)
        with caplog.at_level(logging.DEBUG, logger="proper"):
            logger.debug("[cable] listening on %s:%s", "localhost", 2301, color="red")
        record = caplog.records[-1]
        assert record.name == "proper"
        assert record.getMessage() == "[cable] listening on localhost:2301"
        assert record.color == "red"

    def test_an_event_under_the_level_is_not_built(self, caplog):
        logger.setLevel(logging.INFO)
        assert logger.debug("not %s", "built") is None
        assert not caplog.records
        logger.setLevel(logging.DEBUG)


class TestTheOutput:
    def test_json_has_the_request_id_in_every_logger(self, capsys):
        client = TestClient(make_app(LOG_FORMAT="json", LOG_LEVEL="info"))
        client.get("/", headers={"x-request-id": "abc-123"})

        events = [json.loads(line) for line in lines(capsys)]

        hello, query, boom = events
        assert hello["event"] == "hello world"
        assert hello["logger"] == "proper"
        assert hello["level"] == "info"
        assert hello["color"] == "blue"
        assert "timestamp" in hello
        assert query["event"] == "a query"
        assert query["logger"] == "peewee"
        assert {event["request_id"] for event in events} == {"abc-123"}
        assert boom["exception"][0]["exc_type"] == "ZeroDivisionError"

    def test_json_tracebacks_have_no_variables(self, capsys):
        TestClient(make_app(LOG_FORMAT="json")).get("/")
        boom = json.loads(lines(capsys)[-1])
        assert all("locals" not in frame for frame in boom["exception"][0]["frames"])

    def test_console(self, capsys):
        TestClient(make_app(LOG_FORMAT="console", LOG_LEVEL="info")).get(
            "/", headers={"x-request-id": "abc-123"}
        )
        out = "\n".join(lines(capsys))
        assert "Z [info]  hello world  color=blue\n" in out
        assert "Z [warning] a query  logger=peewee" in out
        assert "Z [error] boom" in out
        assert "ZeroDivisionError: division by zero" in out
        # the short line leaves the request ID to the JSON
        assert "abc-123" not in out

    def test_no_fields_from_another_handler(self, capsys):
        setup_logging("json")
        record = logging.LogRecord("proper", logging.WARNING, __file__, 1, "hi", None, None)
        record.color = "blue"
        logging.Formatter("%(asctime)s %(message)s").format(record)
        event = json.loads(logs._handler.format(record))
        assert event["color"] == "blue"
        assert "message" not in event
        assert "asctime" not in event

    def test_outside_a_request_there_is_no_request_id(self, capsys):
        setup_logging("json")
        logger.warning("alone")
        event = json.loads(lines(capsys)[-1])
        assert event["event"] == "alone"
        assert "request_id" not in event

    def test_off_adds_no_handler(self, capsys):
        setup_logging("json")
        setup_logging("off")
        setup_logging("off")
        assert logs._handler is None
        logger.warning("nowhere")
        assert capsys.readouterr().err == ""

    def test_one_handler_however_many_apps(self):
        make_app(LOG_FORMAT="json")
        make_app(LOG_FORMAT="console")
        root = logging.getLogger()
        assert root.handlers.count(logs._handler) == 1


class TestTheConsoleLine:
    EVENT = {
        "timestamp": "2026-10-24T19:53:02.464472Z",
        "level": "info",
        "event": "Order paid",
        "logger": "proper",
        "request_id": "abc",
        "agent": "curl 8",
        "count": 3,
        "id": "x",
    }

    def render(self, colors=False, **event):
        return _console_renderer(colors=colors)(None, "", {**self.EVENT, **event})

    def test_the_time_the_level_the_event_and_the_fields(self):
        assert self.render() == "19:53:02.464472Z [info]  Order paid  agent='curl 8' count=3 id=x"

    def test_the_levels_line_up_up_to_error(self):
        assert self.render(level="error").startswith("19:53:02.464472Z [error] Order paid  ")
        assert self.render(level="debug").startswith("19:53:02.464472Z [debug] Order paid  ")
        assert self.render(level="warning").startswith("19:53:02.464472Z [warning] Order paid  ")

    def test_a_line_without_fields_has_no_trailing_spaces(self):
        event = {"timestamp": "2026-10-24T19:53:02.464472Z", "level": "info", "event": "hi"}
        assert _console_renderer(colors=False)(None, "", event) == "19:53:02.464472Z [info]  hi"

    def test_only_the_level_has_a_color(self):
        line = self.render(colors=True, level="warning")
        assert line == (
            "19:53:02.464472Z [\x1b[33m\x1b[1mwarning\x1b[0m] Order paid  agent='curl 8' count=3 id=x"
        )


class TestTheConfig:
    def test_follows_debug(self):
        assert make_app(DEBUG=True).config.LOG_FORMAT == "console"
        assert make_app(DEBUG=False).config.LOG_FORMAT == "json"

    def test_an_explicit_format_wins(self):
        assert make_app(DEBUG=True, LOG_FORMAT="json").config.LOG_FORMAT == "json"

    def test_an_unknown_format_is_an_error(self):
        with pytest.raises(ConfigError, match="LOG_FORMAT"):
            make_app(LOG_FORMAT="xml")

    def test_the_level_sets_the_loggers_level(self):
        make_app(LOG_LEVEL="debug")
        assert logger.level == logging.DEBUG
        make_app(LOG_LEVEL="info")
        assert logger.level == logging.INFO

    def test_an_unknown_level_is_an_error(self):
        with pytest.raises(ConfigError, match="LOG_LEVEL"):
            make_app(LOG_LEVEL="verbose")
