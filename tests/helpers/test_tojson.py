import datetime
import json

import pytest

from proper.helpers import to_json


def test_plain_values_are_written_as_json_does():
    value = {"a": [1, 2.5, "ñ", True, None], "b": {"c": "d"}}
    assert to_json(value) == json.dumps(value)


def test_dates_are_written_as_iso_strings():
    value = {
        "day": datetime.date(2026, 11, 22),
        "when": datetime.datetime(2026, 11, 22, 10, 30),
        "aware": datetime.datetime(2026, 11, 22, 10, 30, tzinfo=datetime.UTC),
        "list": [datetime.date(2026, 1, 2)],
    }
    assert json.loads(to_json(value)) == {
        "day": "2026-11-22",
        "when": "2026-11-22T10:30:00",
        "aware": "2026-11-22T10:30:00+00:00",
        "list": ["2026-01-02"],
    }


def test_a_date_on_its_own():
    assert to_json(datetime.date(2026, 11, 22)) == '"2026-11-22"'


def test_other_values_are_refused():
    with pytest.raises(TypeError, match="Object of type set is not JSON serializable"):
        to_json({"tags": {"a"}})
