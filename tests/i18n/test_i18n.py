import datetime

import pytest
from markupsafe import Markup

from proper.errors import TranslationsNotFound
from proper.i18n import I18n
from proper.i18n.formatters import Formatters
from proper.i18n.reader import Reader, deep_update


@pytest.fixture()
def locale_dir(tmp_path):
    """Create a temp directory with YAML locale files."""
    en = tmp_path / "en.yml"
    en.write_text(
        "en:\n"
        "  greeting: 'hello {name}'\n"
        "  farewell: goodbye\n"
        "  nested:\n"
        "    deep: 'deep value'\n"
        "  apples:\n"
        "    one: '{count} apple'\n"
        "    other: '{count} apples'\n"
        "  raw_list:\n"
        "    - a\n"
        "    - b\n"
    )
    es = tmp_path / "es.yml"
    es.write_text("es:\n  greeting: 'hola {name}'\n  farewell: adiós\n")
    return tmp_path


@pytest.fixture()
def locale_dir_territory(tmp_path):
    """Locale dir with territory-specific overrides."""
    en = tmp_path / "en.yml"
    en.write_text("en:\n  color: color\n  greeting: hello\n")
    en_gb = tmp_path / "en_GB.yml"
    en_gb.write_text("en_GB:\n  color: colour\n")
    return tmp_path


@pytest.fixture()
def i18n(locale_dir):
    return I18n(locale_dir)


# --- deep_update ---


def test_shallow_merge():
    source = {"a": 1, "b": 2}
    deep_update(source, {"b": 3, "c": 4})
    assert source == {"a": 1, "b": 3, "c": 4}


def test_nested_merge():
    source = {"a": {"x": 1, "y": 2}}
    deep_update(source, {"a": {"y": 3, "z": 4}})
    assert source == {"a": {"x": 1, "y": 3, "z": 4}}


def test_override_non_dict_with_non_dict():
    source = {"a": 1}
    deep_update(source, {"a": 2})
    assert source == {"a": 2}


def test_override_dict_with_non_dict():
    source = {"a": {"nested": True}}
    deep_update(source, {"a": "flat"})
    assert source == {"a": "flat"}


# --- Reader ---


def test_processes_paths(locale_dir):
    reader = Reader(locale_dir)
    assert locale_dir.resolve() in reader.paths


def test_ignores_nonexistent_paths(tmp_path):
    reader = Reader(tmp_path / "nope")
    assert reader.paths == []


def test_file_path_uses_parent(locale_dir):
    reader = Reader(locale_dir / "en.yml")
    assert locale_dir.resolve() in reader.paths


def test_load_yaml(locale_dir):
    reader = Reader(locale_dir)
    translations = reader.load()
    assert "en" in translations
    assert "es" in translations
    assert translations["en"]["greeting"] == "hello {name}"
    assert translations["es"]["farewell"] == "adiós"


def test_load_empty_dir(tmp_path):
    reader = Reader(tmp_path)
    translations = reader.load()
    assert translations == {}


def test_load_merges_multiple_files(tmp_path):
    (tmp_path / "a.yml").write_text("en:\n  a: 1\n")
    (tmp_path / "b.yml").write_text("en:\n  b: 2\n")
    reader = Reader(tmp_path)
    translations = reader.load()
    assert translations["en"]["a"] == 1
    assert translations["en"]["b"] == 2


def test_load_from_subdirectories(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "en.yml").write_text("en:\n  sub_key: val\n")
    reader = Reader(tmp_path)
    translations = reader.load()
    assert translations["en"]["sub_key"] == "val"


# --- I18n init and properties ---


def test_default_locale(locale_dir):
    i18n = I18n(locale_dir)
    assert i18n.default_locale == "en"


def test_custom_default_locale(locale_dir):
    i18n = I18n(locale_dir, default_locale="es")
    assert i18n.default_locale == "es"


def test_paths_property(locale_dir):
    i18n = I18n(locale_dir)
    assert locale_dir.resolve() in i18n.paths


def test_translations_lazy_loaded(locale_dir):
    i18n = I18n(locale_dir)
    assert i18n._translations is None
    _ = i18n.translations
    assert i18n._translations is not None


def test_translations_setter(locale_dir):
    i18n = I18n(locale_dir)
    custom = {"en": {"hello": "world"}}
    i18n.translations = custom
    assert i18n._translations is custom


def test_callable_shortcut(i18n):
    result = i18n("greeting", name="world", locale="en")
    assert result == Markup("hello world")


# --- I18n translate ---


def test_simple_key(i18n):
    assert i18n.translate("farewell", locale="en") == Markup("goodbye")


def test_with_interpolation(i18n):
    result = i18n.translate("greeting", locale="en", name="Alice")
    assert result == Markup("hello Alice")


def test_nested_key(i18n):
    result = i18n.translate("nested.deep", locale="en")
    assert result == Markup("deep value")


def test_missing_key(i18n):
    result = i18n.translate("nonexistent", locale="en")
    assert "missing:nonexistent" in str(result)


def test_different_locale(i18n):
    result = i18n.translate("farewell", locale="es")
    assert result == Markup("adiós")


def test_returns_non_string_as_is(i18n):
    result = i18n.translate("raw_list", locale="en")
    assert isinstance(result, list)
    assert result == ["a", "b"]


def test_empty_translations_returns_key():
    i18n = I18n.__new__(I18n)
    i18n._translations = {}
    i18n.default_locale = "en"
    result = i18n.translate("some.key")
    assert result == "some.key"


def test_locale_not_found_raises(i18n):
    with pytest.raises(TranslationsNotFound):
        i18n.translate("greeting", locale="ja")


# --- I18n pluralization ---


def test_count_one(i18n):
    result = i18n.translate("apples", count=1, locale="en")
    assert result == Markup("1 apple")


def test_count_many(i18n):
    result = i18n.translate("apples", count=5, locale="en")
    assert result == Markup("5 apples")


def test_count_zero_falls_to_other(i18n):
    result = i18n.translate("apples", count=0, locale="en")
    assert result == Markup("0 apples")


def test_explicit_zero_key():
    i18n = I18n.__new__(I18n)
    i18n._translations = {
        "en": {
            "items": {
                "zero": "no items",
                "one": "{count} item",
                "other": "{count} items",
            }
        }
    }
    i18n.default_locale = "en"
    result = i18n.translate("items", count=0, locale="en")
    assert result == Markup("no items")


def test_exact_count_key():
    i18n = I18n.__new__(I18n)
    i18n._translations = {
        "en": {
            "things": {
                3: "exactly three",
                "other": "some things",
            }
        }
    }
    i18n.default_locale = "en"
    result = i18n.translate("things", count=3, locale="en")
    assert result == Markup("exactly three")


# --- I18n territory fallback ---


def test_territory_specific_overrides(locale_dir_territory):
    i18n = I18n(locale_dir_territory)
    result = i18n.translate("color", locale="en_GB")
    assert result == Markup("colour")


def test_territory_falls_back_to_language(locale_dir_territory):
    i18n = I18n(locale_dir_territory)
    result = i18n.translate("greeting", locale="en_GB")
    assert result == Markup("hello")


def test_base_locale_unaffected(locale_dir_territory):
    i18n = I18n(locale_dir_territory)
    result = i18n.translate("color", locale="en")
    assert result == Markup("color")


# --- I18n negotiate_locale ---


def test_finds_match(i18n):
    assert i18n.negotiate_locale(["fr", "es", "en"]) == "es"


def test_returns_none_when_no_match(i18n):
    assert i18n.negotiate_locale(["ja", "zh"]) is None


def test_returns_first_match(i18n):
    assert i18n.negotiate_locale(["en", "es"]) == "en"


# --- I18n test_for_incomplete_locales ---


def test_detects_missing_keys(i18n):
    # Force translations to load before calling test_for_incomplete_locales
    _ = i18n.translations
    missing = i18n.test_for_incomplete_locales("en", "es")
    assert "es" in missing
    # es is missing keys that en has (nested.deep, apples.*, raw_list)
    assert len(missing["es"]) > 0


def test_no_missing_when_identical(tmp_path):
    (tmp_path / "en.yml").write_text("en:\n  a: 1\n")
    (tmp_path / "es.yml").write_text("es:\n  a: 1\n")
    i18n = I18n(tmp_path)
    _ = i18n.translations
    missing = i18n.test_for_incomplete_locales("en", "es")
    assert missing == {}


# --- I18n lazy_translate ---


def test_lazy_wrapper_repr(i18n):
    LazyWrapper = i18n.lazy_translate
    lazy = LazyWrapper("farewell", locale="en")
    assert repr(lazy) == "goodbye"


def test_lazy_with_interpolation(i18n):
    LazyWrapper = i18n.lazy_translate
    lazy = LazyWrapper("greeting", locale="en", name="Bob")
    assert repr(lazy) == "hello Bob"


# --- format methods ---


def test_format_date(i18n):
    d = datetime.date(2024, 3, 15)
    result = i18n.format_date(d, locale="en")
    assert "Mar" in result
    assert "15" in result
    assert "2024" in result


def test_format_date_locale(i18n):
    d = datetime.date(2024, 3, 15)
    result = i18n.format_date(d, locale="es")
    assert "mar" in result.lower()


def test_format_time(i18n):
    t = datetime.time(15, 30)
    result = i18n.format_time(t, locale="en", timezone="UTC")
    assert "30" in result


def test_format_datetime(i18n):
    dt = datetime.datetime(2024, 3, 15, 10, 30)
    result = i18n.format_datetime(dt, locale="en", timezone="UTC")
    assert "Mar" in result
    assert "2024" in result


def test_format_timedelta(i18n):
    delta = datetime.timedelta(days=365)
    result = i18n.format_timedelta(delta, locale="en")
    assert "year" in result


def test_format_decimal(i18n):
    result = i18n.format_decimal(1234.5, locale="en")
    assert "1,234.5" in result


def test_format_decimal_german(i18n):
    result = i18n.format_decimal(1234.5, locale="de")
    assert "1.234,5" in result


def test_format_percent(i18n):
    result = i18n.format_percent(0.25, locale="en")
    assert "25%" in result


def test_format_currency(i18n):
    result = i18n.format_currency(9.99, "USD", locale="en")
    assert "$" in result
    assert "9.99" in result


def test_format_list(i18n):
    result = i18n.format_list(["a", "b", "c"], locale="en")
    assert "a, b, and c" in result


def test_get_day_names(i18n):
    # Returns list of keys (ints 0-6); verifies the method runs and returns 7 days
    names = i18n.get_day_names("wide", locale="en")
    assert len(names) == 7


def test_get_month_names(i18n):
    # Returns list of keys (ints 1-12); verifies the method runs and returns 12 months
    names = i18n.get_month_names("wide", locale="en")
    assert len(names) == 12


def test_get_currency_name(i18n):
    name = i18n.get_currency_name("USD", locale="en")
    assert "Dollar" in name


def test_get_currency_symbol(i18n):
    symbol = i18n.get_currency_symbol("EUR", locale="en")
    assert "€" in symbol


def test_get_current_locale_default():
    mixin = Formatters()
    assert mixin.get_current_locale() == "en"


def test_get_current_timezone_default():
    mixin = Formatters()
    tz = mixin.get_current_timezone()
    assert str(tz) == "UTC"


def test_format_skeleton(i18n):
    dt = datetime.datetime(2024, 3, 15, 10, 30)
    result = i18n.format_skeleton(dt, "yMMMd", locale="en", timezone="UTC")
    assert "Mar" in result
    assert "15" in result
    assert "2024" in result


def test_format_interval(i18n):
    start = datetime.date(2024, 1, 15)
    end = datetime.date(2024, 1, 17)
    result = i18n.format_interval(start, end, "yMd", locale="en")
    assert "2024" in result
    assert "\u2009\u2013\u2009" in result or "–" in result


def test_format_compact_decimal(i18n):
    result = i18n.format_compact_decimal(12345, format_type="short", locale="en")
    assert "12K" in result


def test_format_compact_currency(i18n):
    result = i18n.format_compact_currency(12345, "USD", locale="en")
    assert "$" in result
    assert "12K" in result


def test_format_scientific(i18n):
    result = i18n.format_scientific(10000, locale="en")
    assert "1E4" in result


def test_get_quarter_names(i18n):
    names = i18n.get_quarter_names("wide", locale="en")
    assert len(names) == 4


def test_get_era_names(i18n):
    names = i18n.get_era_names("wide", locale="en")
    assert len(names) == 2
