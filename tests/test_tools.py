from unittest.mock import MagicMock, patch

import pytest
from huey import MemoryHuey

from proper import App
from proper.cache import NoCache
from proper.emails import ToConsoleMailer
from proper.errors import ConfigError
from proper.helpers import DotDict
from proper.tools import auth, cache, db, i18n, mailer, queue, storage


def _make_app(**overrides):
    config = {
        "SECRET_KEYS": ["*" * 50],
        "DEBUG": False,
        **overrides,
    }
    return App(__name__, config)


def test_all_tools_attached_after_init():
    app = _make_app()
    assert hasattr(app, "auth")
    assert hasattr(app, "cache")
    assert hasattr(app, "db")
    assert hasattr(app, "mailer")
    assert hasattr(app, "queue")
    assert hasattr(app, "i18n")
    # Storage no longer attaches a singleton to `app`; the entry point is
    # `app.attachment_for(...)` from the App class itself.
    assert hasattr(app, "attachment_for")


def test_db_is_dict():
    app = _make_app()
    assert isinstance(app.db, dict)


# --- tools.auth ---


def test_auth_defaults():
    app = _make_app()
    assert app.config.AUTH_PASSWORD_MINLEN == 9
    assert app.config.AUTH_PASSWORD_MAXLEN == 1024
    assert app.config.AUTH_HASH_NAME is None
    assert app.config.AUTH_ROUNDS is None


def test_creates_auth_instance():
    app = _make_app()
    assert hasattr(app, "auth")
    assert app.auth is not None


def test_user_overrides_preserved():
    app = _make_app(AUTH_PASSWORD_MINLEN=12)
    assert app.config.AUTH_PASSWORD_MINLEN == 12


def test_auth_valid_config_passes():
    config = DotDict({**auth.DEFAULT_CONFIG, "SECRET_KEYS": ["*" * 50]})
    auth.validate_config(config)  # should not raise


def test_auth_class_must_be_str_or_type():
    config = DotDict({**auth.DEFAULT_CONFIG, "AUTH_CLASS": 42})
    with pytest.raises(ConfigError, match="AUTH_CLASS"):
        auth.validate_config(config)


def test_auth_hash_name_must_be_str_or_none():
    config = DotDict({**auth.DEFAULT_CONFIG, "AUTH_HASH_NAME": 42})
    with pytest.raises(ConfigError, match="AUTH_HASH_NAME"):
        auth.validate_config(config)


def test_auth_hash_name_none_is_valid():
    config = DotDict({**auth.DEFAULT_CONFIG})
    config.AUTH_HASH_NAME = None
    auth.validate_config(config)


def test_auth_rounds_must_be_positive_int_or_none():
    config = DotDict({**auth.DEFAULT_CONFIG, "AUTH_ROUNDS": -1})
    with pytest.raises(ConfigError, match="AUTH_ROUNDS"):
        auth.validate_config(config)


def test_auth_rounds_zero_is_invalid():
    config = DotDict({**auth.DEFAULT_CONFIG, "AUTH_ROUNDS": 0})
    with pytest.raises(ConfigError, match="AUTH_ROUNDS"):
        auth.validate_config(config)


def test_auth_rounds_string_is_invalid():
    config = DotDict({**auth.DEFAULT_CONFIG, "AUTH_ROUNDS": "10"})
    with pytest.raises(ConfigError, match="AUTH_ROUNDS"):
        auth.validate_config(config)


def test_auth_rounds_none_is_valid():
    config = DotDict({**auth.DEFAULT_CONFIG})
    config.AUTH_ROUNDS = None
    auth.validate_config(config)


def test_password_minlen_must_be_positive_int():
    config = DotDict({**auth.DEFAULT_CONFIG, "AUTH_PASSWORD_MINLEN": 0})
    with pytest.raises(ConfigError, match="AUTH_PASSWORD_MINLEN"):
        auth.validate_config(config)


def test_password_maxlen_must_be_positive_int():
    config = DotDict({**auth.DEFAULT_CONFIG, "AUTH_PASSWORD_MAXLEN": -5})
    with pytest.raises(ConfigError, match="AUTH_PASSWORD_MAXLEN"):
        auth.validate_config(config)


def test_token_life_must_be_positive_int():
    config = DotDict({**auth.DEFAULT_CONFIG, "AUTH_TOKEN_LIFE": 0})
    with pytest.raises(ConfigError, match="AUTH_TOKEN_LIFE"):
        auth.validate_config(config)


# --- tools.cache ---


def test_default_nocache():
    app = _make_app()
    assert isinstance(app.cache, NoCache)


def test_cache_attached_to_catalog():
    app = _make_app()
    assert app.catalog.jinja_env.app_cache is app.cache  # type: ignore


def test_cache_db_registered_if_present():
    """If the cache instance has a .database attr, it is added to app.db."""
    mock_db = MagicMock()

    with patch("proper.tools.cache.get_instance") as mock_get:
        mock_cache = MagicMock()
        mock_cache.database = mock_db
        mock_get.return_value = mock_cache

        app = _make_app(CACHE={"type": "proper.cache.NoCache"})

    assert app.db.get("proper_cache") is mock_db


def test_cache_config():
    cache.validate_config({"type": "proper.cache.NoCache"})

    with pytest.raises(ConfigError, match="CACHE config must be a dictionary"):
        cache.validate_config("not a dict")

    with pytest.raises(ConfigError, match="must have a 'type' key"):
        cache.validate_config({})

    with pytest.raises(ConfigError, match="must be a string or a class"):
        cache.validate_config({"type": 42})


# --- tools.db ---


def test_default_sqlite_memory():
    app = _make_app()
    assert "main" in app.db
    assert app.db["main"] is not None


def test_none_db_config_skipped():
    app = _make_app(DATABASES={"main": None})
    assert "main" not in app.db


def test_custom_db_config():
    app = _make_app(
        DATABASES={
            "main": {
                "type": "playhouse.sqlite_ext.SqliteExtDatabase",
                "database": ":memory:",
            },
            "secondary": {
                "type": "playhouse.sqlite_ext.SqliteExtDatabase",
                "database": ":memory:",
            },
        }
    )
    assert "main" in app.db
    assert "secondary" in app.db


def test_valid_db_config():
    db.validate_config(
        {
            "main": {
                "type": "playhouse.sqlite_ext.SqliteExtDatabase",
                "database": ":memory:",
            }
        }
    )


def test_db_config_must_be_dict():
    with pytest.raises(ConfigError, match="DATABASES config must be a dictionary"):
        db.validate_config("not a dict")


def test_db_config_entry_must_be_dict_or_none():
    with pytest.raises(ConfigError, match="must be a dictionary or None"):
        db.validate_config({"main": "sqlite:///db.sqlite3"})


def test_db_config_entry_must_have_type():
    with pytest.raises(ConfigError, match="must have a 'type' key"):
        db.validate_config({"main": {"database": ":memory:"}})


def test_db_config_entry_type_must_be_str_or_class():
    with pytest.raises(ConfigError, match="must be a string or a class"):
        db.validate_config({"main": {"type": 42, "database": ":memory:"}})


def test_db_config_entry_must_have_database():
    with pytest.raises(ConfigError, match="must have a 'database' key"):
        db.validate_config({"main": {"type": "playhouse.sqlite_ext.SqliteExtDatabase"}})


def test_db_config_entry_database_must_be_str():
    with pytest.raises(ConfigError, match="must be a string"):
        db.validate_config(
            {
                "main": {
                    "type": "playhouse.sqlite_ext.SqliteExtDatabase",
                    "database": 42,
                }
            }
        )


def test_db_confignone_entry_passes():
    db.validate_config({"main": None})


def test_db_config_falsy_entry_passes():
    """Empty dict / 0 / False are all falsy - skipped."""
    db.validate_config({"main": {}})


# --- tools.i18n ---


def test_i18n_no_locales_dir_still_constructs_instance():
    app = _make_app()
    # Even without a locales dir, i18n is constructed so the Babel-backed
    # formatter filters work; only the translation map is empty.
    assert app.i18n is not None
    assert app.i18n.translations == {}


def test_i18n_sets_defaults_when_locales_exist(tmp_path):
    """When locales_path exists, default config values are applied."""
    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    (locales_dir / "en.yml").write_text("hello: Hello")

    app = _make_app()
    # Manually call setup after patching locales_path
    app.locales_path = locales_dir
    i18n.setup(app)

    assert app.config.LOCALE_DEFAULT == "en"
    assert app.config.TIMEZONE_DEFAULT == "UTC"
    assert app.i18n is not None


def test_i18n_registers_jinja_filters(tmp_path):
    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    (locales_dir / "en.yml").write_text("hello: Hello")

    app = _make_app()
    app.locales_path = locales_dir
    i18n.setup(app)

    filters = app.catalog.jinja_env.filters
    assert "format_datetime" in filters
    assert "format_date" in filters
    assert "format_currency" in filters


def test_i18n_registers_jinja_global(tmp_path):
    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    (locales_dir / "en.yml").write_text("hello: Hello")

    app = _make_app()
    app.locales_path = locales_dir
    i18n.setup(app)

    assert "_" in app.catalog.jinja_env.globals


# --- tools.mailer ---


def test_default_to_console_mailer():
    app = _make_app()
    assert isinstance(app.mailer, ToConsoleMailer)


def test_mailer_default_options_set():
    app = _make_app()
    opts = app.config.MAILER_DEFAULT_OPTIONS
    assert opts["from"] == "no-reply@example.com"


def test_valid_mailer_config():
    mailer.validate_config({"type": "proper.emails.ToConsoleMailer"})


def test_mailer_config_must_be_dict():
    with pytest.raises(ConfigError, match="MAILER config must be a dictionary"):
        mailer.validate_config("not a dict")


def test_mailer_config_must_have_type():
    with pytest.raises(ConfigError, match="must have a 'type' key"):
        mailer.validate_config({})


def test_mailer_type_must_be_str_or_class():
    with pytest.raises(ConfigError, match="must be a string or a class"):
        mailer.validate_config({"type": 42})


# --- tools.queue ---


def test_default_memory_huey():
    app = _make_app()
    assert isinstance(app.queue, MemoryHuey)


def test_queue_consumer_config_defaults_applied():
    app = _make_app()
    consumer = app.config.QUEUE_CONSUMER
    assert consumer["workers"] == 1
    assert consumer["periodic"] is True
    assert consumer["worker_type"] == "thread"


def test_queue_consumer_config_user_override():
    app = _make_app(QUEUE_CONSUMER={"workers": 4})
    assert app.config.QUEUE_CONSUMER["workers"] == 4
    # Other defaults are still present
    assert app.config.QUEUE_CONSUMER["periodic"] is True


def test_sqlite_huey_renames_database_to_filename():
    with patch("proper.tools.queue.get_instance") as mock_get:
        mock_get.return_value = MagicMock()
        _make_app(
            QUEUE={
                "type": "huey.SqliteHuey",
                "database": "/tmp/test.db",
            }
        )
        call_kwargs = mock_get.call_args[1]
        assert "filename" in call_kwargs
        assert "database" not in call_kwargs
        assert call_kwargs["filename"] == "/tmp/test.db"


def test_sqlite_huey_without_database_key():
    with patch("proper.tools.queue.get_instance") as mock_get:
        mock_get.return_value = MagicMock()
        _make_app(QUEUE={"type": "huey.SqliteHuey"})
        call_kwargs = mock_get.call_args[1]
        assert "filename" not in call_kwargs
        assert "database" not in call_kwargs


def test_sql_huey_with_dbtype():
    mock_db = MagicMock()
    with patch("proper.tools.queue.get_instance") as mock_get:
        # First call: get_instance for the dbtype → returns mock_db
        # Second call: get_instance for the queue itself → returns mock queue
        mock_get.side_effect = [mock_db, MagicMock()]
        app = _make_app(
            QUEUE={
                "type": "huey.contrib.sql_huey.SqlHuey",
                "dbtype": "peewee.SqliteDatabase",
                "database": ":memory:",
                "host": "localhost",
                "port": 5432,
                "user": "admin",
                "password": "secret",
            }
        )
        # The db instance is registered on app.db
        assert app.db["proper_queue"] is mock_db
        # First get_instance call was for the dbtype
        first_call = mock_get.call_args_list[0]
        assert first_call[1]["type"] == "peewee.SqliteDatabase"
        assert first_call[1]["database"] == ":memory:"


def test_sql_huey_without_dbtype():
    with patch("proper.tools.queue.get_instance") as mock_get:
        mock_get.return_value = MagicMock()
        _make_app(QUEUE={"type": "huey.contrib.sql_huey.SqlHuey"})
        # Only one get_instance call (for the queue itself), no db setup
        assert mock_get.call_count == 1


def test_valid_queue_config():
    queue.validate_config({"type": "huey.MemoryHuey"})


def test_queue_config_must_be_dict():
    with pytest.raises(ConfigError, match="QUEUE config must be a dictionary"):
        queue.validate_config("not a dict")


def test_queue_config_must_have_type():
    with pytest.raises(ConfigError, match="must have a 'type' key"):
        queue.validate_config({})


def test_queue_type_must_be_str_or_class():
    with pytest.raises(ConfigError, match="must be a string or a class"):
        queue.validate_config({"type": 42})


def test_queue_dbtype_must_be_str_or_class():
    with pytest.raises(ConfigError, match="dbtype"):
        queue.validate_config({"type": "huey.MemoryHuey", "dbtype": 42})


def test_queue_dbtype_string_is_valid():
    queue.validate_config(
        {
            "type": "huey.contrib.sql_huey.SqlHuey",
            "dbtype": "peewee.SqliteDatabase",
        }
    )


# --- tools.storage ---


def test_storage_default_config_values_set():
    app = _make_app(STORAGE="local")
    assert "STORAGE_SERVICES" in app.config
    assert isinstance(app.config.STORAGE_SERVICES, dict)
    assert "local" in app.config.STORAGE_SERVICES


def test_storage_web_image_content_types_default():
    app = _make_app(STORAGE="local")
    types = app.config.STORAGE_ALLOWED_VARIANTS
    assert "image/png" in types
    assert "image/jpeg" in types


def test_storage_valid_config():
    config = DotDict(
        {
            "STORAGE_SERVICES": {"local": {"type": "Disk", "root": "/tmp"}},
        }
    )
    storage.validate_config(config)


def test_storage_services_must_be_dict():
    config = DotDict({"STORAGE_SERVICES": "not a dict"})
    with pytest.raises(ConfigError, match="STORAGE_SERVICES"):
        storage.validate_config(config)


def test_storage_services_none_is_invalid():
    config = DotDict({"STORAGE_SERVICES": None})
    with pytest.raises(ConfigError, match="STORAGE_SERVICES"):
        storage.validate_config(config)
