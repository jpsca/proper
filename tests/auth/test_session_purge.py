"""Deleting the login sessions nobody can use anymore, and the daily task
that does it."""
import importlib
from datetime import datetime, timedelta

from .conftest import APP_NAME


def _session(models, user, *, expires_in, revoked=False):
    session = models.Session.create_for_user(user)
    session.expires_at = models.base.utcnow() + expires_in
    session.revoked = revoked
    session.save()
    return session


def test_purge_expired_deletes_the_expired_and_the_revoked(models, user):
    live = _session(models, user, expires_in=timedelta(hours=1))
    _session(models, user, expires_in=timedelta(seconds=-1))
    _session(models, user, expires_in=timedelta(days=-90))
    _session(models, user, expires_in=timedelta(hours=1), revoked=True)
    _session(models, user, expires_in=timedelta(hours=-1), revoked=True)

    assert models.Session.purge_expired() == 4

    assert [s.id for s in models.Session.select()] == [live.id]
    assert models.Session.find_by_token(live.token) is not None


def test_purge_expired_with_nothing_to_delete(models, user):
    _session(models, user, expires_in=timedelta(days=1))
    assert models.Session.purge_expired() == 0
    assert models.Session.select().count() == 1


def test_the_users_are_kept(models, user):
    _session(models, user, expires_in=timedelta(days=-1))
    models.Session.purge_expired()
    assert models.User.select().count() == 1


def test_the_task_purges_the_sessions(models, user):
    live = _session(models, user, expires_in=timedelta(hours=1))
    _session(models, user, expires_in=timedelta(hours=-1))
    tasks = importlib.import_module(f"{APP_NAME}.tasks.expired_sessions_sweep")

    tasks.sweep_expired_sessions.call_local()

    assert [s.id for s in models.Session.select()] == [live.id]


def test_the_task_is_imported_with_the_tasks_of_the_app(models):
    tasks = importlib.import_module(f"{APP_NAME}.tasks")
    assert hasattr(tasks, "expired_sessions_sweep")


def test_the_task_runs_every_day(models):
    tasks = importlib.import_module(f"{APP_NAME}.tasks.expired_sessions_sweep")
    task = tasks.sweep_expired_sessions.task_class()
    runs = [
        hour
        for hour in range(24)
        for minute in (0, 30)
        if task.validate_datetime(datetime(2026, 11, 21, hour, minute))
    ]
    assert runs == [4]
