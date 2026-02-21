"""Tests for proper.i18n — Reader, I18n, plural_rules, and BabelMixin."""

import datetime
import decimal

import pytest
from markupsafe import Markup

from proper.errors import TranslationsNotFound
from proper.i18n import I18n
from proper.i18n.plural_rules import (
    cldr_modulo,
    extract_operands,
    in_range_list,
    plural_ar,
    plural_en,
    plural_es,
    plural_fr,
    plural_pl,
    plural_ru,
    within_range_list,
)
from proper.i18n.reader import Reader, deep_update


# ── fixtures ────────────────────────────────────────────────────────


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
    es.write_text(
        "es:\n"
        "  greeting: 'hola {name}'\n"
        "  farewell: adiós\n"
    )
    return tmp_path


@pytest.fixture()
def locale_dir_territory(tmp_path):
    """Locale dir with territory-specific overrides."""
    en = tmp_path / "en.yml"
    en.write_text(
        "en:\n"
        "  color: color\n"
        "  greeting: hello\n"
    )
    en_gb = tmp_path / "en_GB.yml"
    en_gb.write_text(
        "en_GB:\n"
        "  color: colour\n"
    )
    return tmp_path


@pytest.fixture()
def i18n(locale_dir):
    return I18n(locale_dir)


# ═══════════════════════════════════════════════════════════════════
# deep_update
# ═══════════════════════════════════════════════════════════════════


class TestDeepUpdate:
    def test_shallow_merge(self):
        source = {"a": 1, "b": 2}
        deep_update(source, {"b": 3, "c": 4})
        assert source == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        source = {"a": {"x": 1, "y": 2}}
        deep_update(source, {"a": {"y": 3, "z": 4}})
        assert source == {"a": {"x": 1, "y": 3, "z": 4}}

    def test_override_non_dict_with_non_dict(self):
        source = {"a": 1}
        deep_update(source, {"a": 2})
        assert source == {"a": 2}

    def test_override_dict_with_non_dict(self):
        source = {"a": {"nested": True}}
        deep_update(source, {"a": "flat"})
        assert source == {"a": "flat"}


# ═══════════════════════════════════════════════════════════════════
# Reader
# ═══════════════════════════════════════════════════════════════════


class TestReader:
    def test_processes_paths(self, locale_dir):
        reader = Reader(locale_dir)
        assert locale_dir.resolve() in reader.paths

    def test_ignores_nonexistent_paths(self, tmp_path):
        reader = Reader(tmp_path / "nope")
        assert reader.paths == []

    def test_file_path_uses_parent(self, locale_dir):
        reader = Reader(locale_dir / "en.yml")
        assert locale_dir.resolve() in reader.paths

    def test_load_yaml(self, locale_dir):
        reader = Reader(locale_dir)
        translations = reader.load()
        assert "en" in translations
        assert "es" in translations
        assert translations["en"]["greeting"] == "hello {name}"
        assert translations["es"]["farewell"] == "adiós"

    def test_load_empty_dir(self, tmp_path):
        reader = Reader(tmp_path)
        translations = reader.load()
        assert translations == {}

    def test_load_merges_multiple_files(self, tmp_path):
        (tmp_path / "a.yml").write_text("en:\n  a: 1\n")
        (tmp_path / "b.yml").write_text("en:\n  b: 2\n")
        reader = Reader(tmp_path)
        translations = reader.load()
        assert translations["en"]["a"] == 1
        assert translations["en"]["b"] == 2

    def test_load_from_subdirectories(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "en.yml").write_text("en:\n  sub_key: val\n")
        reader = Reader(tmp_path)
        translations = reader.load()
        assert translations["en"]["sub_key"] == "val"


# ═══════════════════════════════════════════════════════════════════
# I18n — init and properties
# ═══════════════════════════════════════════════════════════════════


class TestI18nInit:
    def test_default_locale(self, locale_dir):
        i18n = I18n(locale_dir)
        assert i18n.default_locale == "en"

    def test_custom_default_locale(self, locale_dir):
        i18n = I18n(locale_dir, default_locale="es")
        assert i18n.default_locale == "es"

    def test_paths_property(self, locale_dir):
        i18n = I18n(locale_dir)
        assert locale_dir.resolve() in i18n.paths

    def test_translations_lazy_loaded(self, locale_dir):
        i18n = I18n(locale_dir)
        assert i18n._translations is None
        _ = i18n.translations
        assert i18n._translations is not None

    def test_translations_setter(self, locale_dir):
        i18n = I18n(locale_dir)
        custom = {"en": {"hello": "world"}}
        i18n.translations = custom
        assert i18n._translations is custom

    def test_callable_shortcut(self, i18n):
        result = i18n("greeting", name="world", locale="en")
        assert result == Markup("hello world")


# ═══════════════════════════════════════════════════════════════════
# I18n — translate
# ═══════════════════════════════════════════════════════════════════


class TestTranslate:
    def test_simple_key(self, i18n):
        assert i18n.translate("farewell", locale="en") == Markup("goodbye")

    def test_with_interpolation(self, i18n):
        result = i18n.translate("greeting", locale="en", name="Alice")
        assert result == Markup("hello Alice")

    def test_nested_key(self, i18n):
        result = i18n.translate("nested.deep", locale="en")
        assert result == Markup("deep value")

    def test_missing_key(self, i18n):
        result = i18n.translate("nonexistent", locale="en")
        assert "missing:nonexistent" in str(result)

    def test_different_locale(self, i18n):
        result = i18n.translate("farewell", locale="es")
        assert result == Markup("adiós")

    def test_returns_non_string_as_is(self, i18n):
        result = i18n.translate("raw_list", locale="en")
        assert isinstance(result, list)
        assert result == ["a", "b"]

    def test_empty_translations_returns_key(self):
        i18n = I18n.__new__(I18n)
        i18n._translations = {}
        i18n.default_locale = "en"
        result = i18n.translate("some.key")
        assert result == "some.key"

    def test_locale_not_found_raises(self, i18n):
        with pytest.raises(TranslationsNotFound):
            i18n.translate("greeting", locale="ja")


# ═══════════════════════════════════════════════════════════════════
# I18n — pluralization
# ═══════════════════════════════════════════════════════════════════


class TestPluralize:
    def test_count_one(self, i18n):
        result = i18n.translate("apples", count=1, locale="en")
        assert result == Markup("1 apple")

    def test_count_many(self, i18n):
        result = i18n.translate("apples", count=5, locale="en")
        assert result == Markup("5 apples")

    def test_count_zero_falls_to_other(self, i18n):
        result = i18n.translate("apples", count=0, locale="en")
        assert result == Markup("0 apples")

    def test_explicit_zero_key(self):
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

    def test_exact_count_key(self):
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


# ═══════════════════════════════════════════════════════════════════
# I18n — territory fallback
# ═══════════════════════════════════════════════════════════════════


class TestTerritoryFallback:
    def test_territory_specific_overrides(self, locale_dir_territory):
        i18n = I18n(locale_dir_territory)
        result = i18n.translate("color", locale="en_GB")
        assert result == Markup("colour")

    def test_territory_falls_back_to_language(self, locale_dir_territory):
        i18n = I18n(locale_dir_territory)
        result = i18n.translate("greeting", locale="en_GB")
        assert result == Markup("hello")

    def test_base_locale_unaffected(self, locale_dir_territory):
        i18n = I18n(locale_dir_territory)
        result = i18n.translate("color", locale="en")
        assert result == Markup("color")


# ═══════════════════════════════════════════════════════════════════
# I18n — negotiate_locale
# ═══════════════════════════════════════════════════════════════════


class TestNegotiateLocale:
    def test_finds_match(self, i18n):
        assert i18n.negotiate_locale(["fr", "es", "en"]) == "es"

    def test_returns_none_when_no_match(self, i18n):
        assert i18n.negotiate_locale(["ja", "zh"]) is None

    def test_returns_first_match(self, i18n):
        assert i18n.negotiate_locale(["en", "es"]) == "en"


# ═══════════════════════════════════════════════════════════════════
# I18n — test_for_incomplete_locales
# ═══════════════════════════════════════════════════════════════════


class TestIncompleteLocales:
    def test_detects_missing_keys(self, i18n):
        # Force translations to load before calling test_for_incomplete_locales
        _ = i18n.translations
        missing = i18n.test_for_incomplete_locales("en", "es")
        assert "es" in missing
        # es is missing keys that en has (nested.deep, apples.*, raw_list)
        assert len(missing["es"]) > 0

    def test_no_missing_when_identical(self, tmp_path):
        (tmp_path / "en.yml").write_text("en:\n  a: 1\n")
        (tmp_path / "es.yml").write_text("es:\n  a: 1\n")
        i18n = I18n(tmp_path)
        _ = i18n.translations
        missing = i18n.test_for_incomplete_locales("en", "es")
        assert missing == {}


# ═══════════════════════════════════════════════════════════════════
# I18n — lazy_translate
# ═══════════════════════════════════════════════════════════════════


class TestLazyTranslate:
    def test_lazy_wrapper_repr(self, i18n):
        LazyWrapper = i18n.lazy_translate
        lazy = LazyWrapper("farewell", locale="en")
        assert repr(lazy) == "goodbye"

    def test_lazy_with_interpolation(self, i18n):
        LazyWrapper = i18n.lazy_translate
        lazy = LazyWrapper("greeting", locale="en", name="Bob")
        assert repr(lazy) == "hello Bob"


# ═══════════════════════════════════════════════════════════════════
# plural_rules — extract_operands
# ═══════════════════════════════════════════════════════════════════


class TestExtractOperands:
    def test_integer(self):
        n, i, v, f, t, e = extract_operands(3)
        assert n == 3
        assert i == 3
        assert v == 0
        assert f == 0
        assert t == 0

    def test_float_whole(self):
        n, i, v, f, t, e = extract_operands(3.0)
        assert n == 3
        assert i == 3
        assert v == 0

    def test_float_fractional(self):
        n, i, v, f, t, e = extract_operands(1.5)
        assert i == 1
        assert v == 1
        assert f == 5
        assert t == 5

    def test_decimal(self):
        D = decimal.Decimal
        n, i, v, f, t, e = extract_operands(D("1.230"))
        assert i == 1
        assert v == 3
        assert f == 230
        assert t == 23

    def test_negative(self):
        n, i, v, f, t, e = extract_operands(-5)
        assert n == 5
        assert i == 5


# ═══════════════════════════════════════════════════════════════════
# plural_rules — range helpers
# ═══════════════════════════════════════════════════════════════════


class TestRangeHelpers:
    def test_in_range_list_integer(self):
        assert in_range_list(1, [(1, 3)]) is True
        assert in_range_list(3, [(1, 3)]) is True
        assert in_range_list(4, [(1, 3)]) is False

    def test_in_range_list_rejects_float(self):
        assert in_range_list(1.5, [(1, 3)]) is False

    def test_in_range_list_multiple_ranges(self):
        assert in_range_list(5, [(1, 3), (5, 8)]) is True

    def test_within_range_list_float(self):
        assert within_range_list(1.5, [(1, 3)]) is True
        assert within_range_list(10, [(1, 4)]) is False

    def test_cldr_modulo_positive(self):
        assert cldr_modulo(7, 3) == 1

    def test_cldr_modulo_negative_dividend(self):
        assert cldr_modulo(-3, 5) == -3

    def test_cldr_modulo_negative_divisor(self):
        assert cldr_modulo(-3, -5) == -3

    def test_cldr_modulo_positive_both(self):
        assert cldr_modulo(3, 5) == 3


# ═══════════════════════════════════════════════════════════════════
# plural_rules — selected language rules
# ═══════════════════════════════════════════════════════════════════


class TestPluralRules:
    def test_english_one(self):
        assert plural_en(1) == "one"

    def test_english_other(self):
        assert plural_en(0) is None
        assert plural_en(2) is None
        assert plural_en(5) is None

    def test_spanish_one(self):
        assert plural_es(1) == "one"

    def test_spanish_many(self):
        # 1000000 has i % 1000000 == 0 and i != 0
        assert plural_es(1000000) == "many"

    def test_spanish_other(self):
        assert plural_es(2) is None

    def test_french_one(self):
        assert plural_fr(0) == "one"
        assert plural_fr(1) == "one"

    def test_french_other(self):
        assert plural_fr(2) is None

    def test_arabic_zero(self):
        assert plural_ar(0) == "zero"

    def test_arabic_one(self):
        assert plural_ar(1) == "one"

    def test_arabic_two(self):
        assert plural_ar(2) == "two"

    def test_arabic_few(self):
        assert plural_ar(3) == "few"
        assert plural_ar(10) == "few"

    def test_arabic_many(self):
        assert plural_ar(11) == "many"
        assert plural_ar(99) == "many"

    def test_arabic_other(self):
        assert plural_ar(100) is None

    def test_russian_one(self):
        assert plural_ru(1) == "one"
        assert plural_ru(21) == "one"

    def test_russian_few(self):
        assert plural_ru(2) == "few"
        assert plural_ru(3) == "few"
        assert plural_ru(4) == "few"
        assert plural_ru(22) == "few"

    def test_russian_many(self):
        assert plural_ru(0) == "many"
        assert plural_ru(5) == "many"
        assert plural_ru(11) == "many"
        assert plural_ru(12) == "many"
        assert plural_ru(14) == "many"

    def test_polish_one(self):
        assert plural_pl(1) == "one"

    def test_polish_few(self):
        assert plural_pl(2) == "few"
        assert plural_pl(3) == "few"
        assert plural_pl(4) == "few"
        assert plural_pl(22) == "few"

    def test_polish_many(self):
        assert plural_pl(0) == "many"
        assert plural_pl(5) == "many"
        assert plural_pl(12) == "many"


# ═══════════════════════════════════════════════════════════════════
# BabelMixin (via I18n which inherits it)
# ═══════════════════════════════════════════════════════════════════


class TestBabelMixin:
    def test_format_date(self, i18n):
        d = datetime.date(2024, 3, 15)
        result = i18n.format_date(d, locale="en")
        assert "Mar" in result
        assert "15" in result
        assert "2024" in result

    def test_format_date_locale(self, i18n):
        d = datetime.date(2024, 3, 15)
        result = i18n.format_date(d, locale="es")
        assert "mar" in result.lower()

    def test_format_time(self, i18n):
        t = datetime.time(15, 30)
        result = i18n.format_time(t, locale="en", timezone="UTC")
        assert "30" in result

    def test_format_datetime(self, i18n):
        dt = datetime.datetime(2024, 3, 15, 10, 30)
        result = i18n.format_datetime(dt, locale="en", timezone="UTC")
        assert "Mar" in result
        assert "2024" in result

    def test_format_timedelta(self, i18n):
        delta = datetime.timedelta(days=365)
        result = i18n.format_timedelta(delta, locale="en")
        assert "year" in result

    def test_format_decimal(self, i18n):
        result = i18n.format_decimal(1234.5, locale="en")
        assert "1,234.5" in result

    def test_format_decimal_german(self, i18n):
        result = i18n.format_decimal(1234.5, locale="de")
        assert "1.234,5" in result

    def test_format_percent(self, i18n):
        result = i18n.format_percent(0.25, locale="en")
        assert "25%" in result

    def test_format_currency(self, i18n):
        result = i18n.format_currency(9.99, "USD", locale="en")
        assert "$" in result
        assert "9.99" in result

    def test_format_list(self, i18n):
        result = i18n.format_list(["a", "b", "c"], locale="en")
        assert "a, b, and c" in result

    def test_get_day_names(self, i18n):
        # Returns list of keys (ints 0-6); verifies the method runs and returns 7 days
        names = i18n.get_day_names("wide", locale="en")
        assert len(names) == 7

    def test_get_month_names(self, i18n):
        # Returns list of keys (ints 1-12); verifies the method runs and returns 12 months
        names = i18n.get_month_names("wide", locale="en")
        assert len(names) == 12

    def test_get_currency_name(self, i18n):
        name = i18n.get_currency_name("USD", locale="en")
        assert "Dollar" in name

    def test_get_currency_symbol(self, i18n):
        symbol = i18n.get_currency_symbol("EUR", locale="en")
        assert "€" in symbol
