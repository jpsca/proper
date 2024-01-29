from pathlib import Path

import pytest
from markupsafe import Markup

from proper.i18n import I18n
from proper.errors import TranslationsNotFound


HERE = Path(__file__).parent
LOCALES1 = HERE / "locales1"
LOCALES2 = HERE / "locales2"
LOCALES_PATHS = [LOCALES1, LOCALES2]


def get_current_locale():
    return None


def test_default_locale():
    i18n = I18n(
        *LOCALES_PATHS, get_current_locale=get_current_locale, default_locale="es-pe"
    )
    assert i18n.default_locale == "es_PE"


def test_load_translations():
    i18n = I18n(*LOCALES_PATHS, get_current_locale=get_current_locale)
    i18n._load_translations()
    trans = i18n.translations
    print(trans)

    assert trans["en"]["greeting"] == "Hello World!"
    assert trans["es"]["greeting"] == "Hola mundo"
    assert trans["es_PE"]["greeting"] == "Habla"


def test_get_current_locale():
    def get_current_locale():
        return "en"

    i18n = I18n(
        *LOCALES_PATHS, get_current_locale=get_current_locale, default_locale="es-pe"
    )
    assert i18n.translate("greeting") == "Hello World!"
    assert i18n.translate("greeting", locale="es") == "Hola mundo"


def test_translate():
    i18n = I18n(
        *LOCALES_PATHS, get_current_locale=get_current_locale, default_locale="es-PE"
    )

    assert i18n.translate("greeting") == "Habla"
    # shortcut, see `I18n.__call__`
    assert i18n("greeting") == "Habla"

    assert i18n.translate("greeting", locale="es") == "Hola mundo"
    assert i18n.translate("with_html", locale="en") == Markup("<b>Hello</b>")


def test_key_not_found():
    i18n = I18n(
        *LOCALES_PATHS, get_current_locale=get_current_locale, default_locale="es-PE"
    )
    assert i18n.translate("bla", locale="es") == "<missing:bla/>"


def test_language_not_found():
    i18n = I18n(
        *LOCALES_PATHS, get_current_locale=get_current_locale, default_locale="es-PE"
    )
    with pytest.raises(TranslationsNotFound):
        i18n.translate("greeting", locale="fr")


def test_translate_pluralize():
    i18n = I18n(
        *LOCALES_PATHS, get_current_locale=get_current_locale, default_locale="es-PE"
    )

    assert i18n.translate("apple", 0, locale="en") == "No apples"
    assert i18n.translate("apple", 1, locale="en") == "One apple"
    assert i18n.translate("apple", 10, locale="en") == "10 apples"


def test_lazy_translate():
    i18n = I18n(
        *LOCALES_PATHS, get_current_locale=get_current_locale, default_locale="es_PE"
    )

    lazy = i18n.lazy_translate("greeting")
    assert lazy != "Habla"
    assert str(lazy) == "Habla"

    lazy = i18n.lazy_translate("greeting", locale="en")
    assert lazy != "Hello World!"
    assert str(lazy) == "Hello World!"


def test_lazy_key_not_found():
    i18n = I18n(
        *LOCALES_PATHS, get_current_locale=get_current_locale, default_locale="es-PE"
    )
    lazy = i18n.lazy_translate("bla", locale="es")
    assert str(lazy) == "<missing:bla/>"


def test_lazy_language_not_found():
    i18n = I18n(
        *LOCALES_PATHS, get_current_locale=get_current_locale, default_locale="es-PE"
    )
    lazy = i18n.lazy_translate("greeting", locale="fr")
    with pytest.raises(TranslationsNotFound):
        str(lazy)


def test_for_incomplete_locales():
    i18n = I18n(*LOCALES_PATHS, get_current_locale=get_current_locale)
    assert i18n.test_for_incomplete_locales()

    i18n.translations = {
        "es": {
            "a": 1,
            "b": {0: "nope", 1: "one"},
            "c": 1,
        },
        "en": {
            "b": {0: "nope"},
            "c": 1,
        },
        "fr": {
            "a": 1,
            "b": {0: "nope"},
            "c": 1,
        },
        "pt": {
            "a": 1,
            "b": {0: "nope", 1: "one"},
            "c": 1,
        },
    }

    expected = {
        "en": set("a b.1".split()),
        "fr": set("b.1".split()),
    }
    assert i18n.test_for_incomplete_locales() == expected

    expected = {
        "en": set(["a"]),
    }
    assert i18n.test_for_incomplete_locales("en", "fr") == expected

    expected = {}
    assert i18n.test_for_incomplete_locales("es", "pt") == expected
