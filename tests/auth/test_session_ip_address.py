"""The IP address stored with each login session: any value
`request.remote_ip` can return, in a new app and in one made before."""

import importlib
import ipaddress
import sys

import peewee as pw
import pytest

from proper.auth.install import AUTH_BLUEPRINT
from proper.cli.db_cli import Router
from proper.concerns import Authentication
from proper.controller import Controller
from proper.core.response import Response
from proper.helpers import render_blueprint
from proper.test_client import make_test_request


APP_NAME = "ipaddrapp"

BASE_MODEL = """\
import peewee as pw
from proper.models import ProperModel

db = pw.SqliteDatabase(":memory:")


class BaseModel(ProperModel):
    class Meta:
        database = db
"""

# The migration in the CHANGELOG, for an app whose `Session` model has
# `ip_address = pw.IPField(null=True)`.
MIGRATION = '''\
import ipaddress

import peewee as pw
from peewee_migrate import Migrator


def ip_numbers_to_text(migrator):
    """`IPField` stored each IPv4 address as a number."""
    Session = migrator.orm["session"]
    for session in Session.select().where(Session.ip_address.is_null(False)):
        session.ip_address = str(ipaddress.IPv4Address(int(session.ip_address)))
        session.save(only=[Session.ip_address])


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    migrator.change_fields("session", ip_address=pw.CharField(max_length=255, null=True))
    migrator.run(ip_numbers_to_text, migrator)


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    # `IPField` takes only IPv4 addresses: the stored addresses are dropped.
    migrator.remove_fields("session", "ip_address")
    migrator.add_fields("session", ip_address=pw.IPField(null=True))
'''


@pytest.fixture()
def models(tmp_path, app):
    """The auth addon's models, as `proper install auth` writes them into
    an app, on an in-memory database."""
    root = tmp_path / APP_NAME
    for folder in ("controllers", "cli", "config", "emails", "forms", "models", "views"):
        (root / folder).mkdir(parents=True)
    (root / "__init__.py").write_text("")
    (root / "main.py").write_text(
        'from proper import App\napp = App(__name__, {"SECRET_KEYS": ["*" * 50]})\n'
    )
    for folder in ("cli", "config", "emails", "models"):
        (root / folder / "__init__.py").write_text("")
    (root / "models" / "base.py").write_text(BASE_MODEL)
    (root / "views" / "nav.jx").write_text("<nav></nav>\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "conftest.py").write_text("")
    render_blueprint(AUTH_BLUEPRINT, tmp_path, context={"app_name": APP_NAME})

    sys.path.insert(0, str(tmp_path))
    try:
        module = importlib.import_module(f"{APP_NAME}.models")
        db = module.base.db
        db.create_tables([module.User, module.Session])
        yield module
        db.close()
    finally:
        sys.path.remove(str(tmp_path))
        for name in list(sys.modules):
            if name == APP_NAME or name.startswith(f"{APP_NAME}."):
                del sys.modules[name]


@pytest.fixture()
def user(models):
    return models.User.create(login="ada@example.com", password="correct horse battery")


@pytest.mark.parametrize(
    "ip, stored",
    [
        ("203.0.113.5", "203.0.113.5"),
        ("2001:db8::1", "2001:db8::1"),
        # The peer of a dual-stack server (Granian on `::`), as it gives it
        ("::ffff:203.0.113.5", "::ffff:203.0.113.5"),
        ("ffff:ffff:ffff:ffff:ffff:ffff:255.255.255.255",) * 2,
        ("fe80::1%eth0", "fe80::1%eth0"),
        # What a proxy writes instead of an address
        ("unknown", "unknown"),
        ("_hidden", "_hidden"),
        ("", None),
        (None, None),
        ("x" * 300, "x" * 255),
    ],
    ids=lambda value: value[:50] if isinstance(value, str) else value,
)
def test_the_session_stores_any_remote_ip(models, user, ip, stored):
    session = models.Session.create_for_user(user, ip_address=ip, user_agent="UA")
    assert models.Session.get_by_id(session.id).ip_address == stored


class _LegacySession(pw.Model):
    """The `Session` model of an app made before: an `IPField`."""

    ip_address = pw.IPField(null=True)

    @classmethod
    def create_for_user(cls, *, user, ip_address, user_agent):
        return cls.create(ip_address=ip_address)


@pytest.fixture()
def legacy_session(db):
    _LegacySession.bind(db)
    db.create_tables([_LegacySession])
    return _LegacySession


def _signed_in_session(app, session_model, client, user=None):
    class SessionController(Authentication, Controller):
        Session = session_model

    request = make_test_request(app=app, client=client)
    controller = SessionController(request, Response(app))
    controller._set_current_session = lambda session: session
    return controller.new_session_for(user=user)


def test_sign_in_with_a_legacy_ip_field_stores_ipv4(app, legacy_session):
    session = _signed_in_session(app, legacy_session, ("203.0.113.5", 5000))
    assert legacy_session.get_by_id(session.id).ip_address == "203.0.113.5"


@pytest.mark.parametrize(
    "peer",
    [
        ("::ffff:203.0.113.5", 5000),
        ("2001:db8::1", 5000),
        ("unknown", None),
        ("_hidden", None),
        None,
    ],
)
def test_sign_in_with_a_legacy_ip_field_needs_the_migration(app, legacy_session, peer):
    """Without the migration in the CHANGELOG, `IPField` can't store
    anything but an IPv4 address: signing in raises (a 500)."""
    with pytest.raises(OSError):
        _signed_in_session(app, legacy_session, peer)


def test_sign_in_stores_the_remote_ip_as_it_is(app, models, user):
    session = _signed_in_session(app, models.Session, ("2001:db8::1", 5000), user)
    assert session.ip_address == "2001:db8::1"


def test_the_migration_from_the_ip_field(tmp_path):
    """The migration in the CHANGELOG, generated and run with `proper db`'s
    `Router`: the numbers become addresses, an IPv6 address can be stored,
    and the rollback goes back to an `IPField`."""
    db = pw.SqliteDatabase(str(tmp_path / "app.sqlite3"))

    def session_model(ip_field):
        class User(pw.Model):
            login = pw.CharField()

            class Meta:
                database = db
                table_name = "user"

        class Session(pw.Model):
            ip_address = ip_field
            user = pw.ForeignKeyField(User, backref="sessions", on_delete="CASCADE")

            class Meta:
                database = db
                table_name = "session"

        return User, Session

    migrations = tmp_path / "db"
    migrations.mkdir()
    router = Router(db, migrate_dir=migrations)
    OldUser, OldSession = session_model(pw.IPField(null=True))
    router.create("users", auto=[OldUser, OldSession])
    router.run()
    user = OldUser.create(login="ada@example.com")
    OldSession.create(ip_address="203.0.113.5", user=user)
    OldSession.create(ip_address=None, user=user)

    # What `proper db create` writes for the new field
    NewUser, NewSession = session_model(pw.CharField(max_length=255, null=True))
    name = router.create("session_ip_address_text", auto=[NewUser, NewSession])
    generated = (migrations / f"{name}.py").read_text()
    assert (
        'migrator.change_fields("session", ip_address=pw.CharField(max_length=255, null=True))'
        in generated
    )

    (migrations / f"{name}.py").write_text(MIGRATION)
    assert Router(db, migrate_dir=migrations).run() == [name]
    assert [s.ip_address for s in NewSession.select().order_by(NewSession.id)] == [
        "203.0.113.5",
        None,
    ]
    NewSession.create(ip_address="2001:db8::1", user=user)
    assert NewSession.get(NewSession.ip_address == "2001:db8::1")

    Router(db, migrate_dir=migrations).rollback()
    assert [s.ip_address for s in OldSession.select()] == [None, None, None]
    OldSession.create(ip_address="198.51.100.7", user=user)
    assert ipaddress.ip_address(
        OldSession.select().order_by(OldSession.id.desc()).get().ip_address
    )
