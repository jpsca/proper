from datetime import UTC, datetime

from proper.models import utcnow


def test_utcnow_is_naive_and_in_utc():
    now = utcnow()
    assert now.tzinfo is None
    assert abs((datetime.now(UTC).replace(tzinfo=None) - now).total_seconds()) < 5
