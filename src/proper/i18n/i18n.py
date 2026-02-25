import datetime
import typing as t
from pathlib import Path

import babel
import babel.dates as babel_dates
from markupsafe import Markup

from ..errors import TranslationsNotFound
from ..global_context import current
from ..helpers import format_locale
from .babel_mixin import BabelMixin
from .reader import Reader


class I18n(BabelMixin):
    __slots__ = (
        "reader",
        "_translations",
        "default_locale",
        "default_timezone"
    )

    _translations: dict[str, t.Any] | None

    def __init__(
        self,
        *paths: Path | str,
        default_locale: str = "en",
        default_timezone: str = "UTC",
    ):
        """Internationalization and localization functions.

        Arguments:
            *paths:
                paths that will be searched for the translations.
            default_locale:
                Fallback locale if the current one is undefined or not available.
                This value will be accepted without checking if it's available.
            default_timezone:
                Fallback timezone if the current one is undefined.

        """
        self.reader = Reader(*paths)
        self._translations = None
        self.default_locale = format_locale(default_locale)
        self.default_timezone = babel_dates.get_timezone(default_timezone)

    def __call__(self, *args, **kwargs) -> t.Any:
        """Calling this instance is a shortcut to calling `self.translate`.
        """
        return self.translate(*args, **kwargs)

    @property
    def translations(self) -> dict[str, t.Any]:
        if self._translations is None:
            self._translations = self.reader.load()
        return self._translations or {}

    @translations.setter
    def translations(self, value: dict[str, t.Any]) -> None:
        """Set the translations directly, bypassing the reader."""
        self._translations = value

    @property
    def paths(self) -> list[Path]:
        return self.reader.paths

    @property
    def lazy_translate(self):
        translate = self.translate

        class LazyWrapper:
            def __init__(
                self,
                key: str,
                count: int = 1,
                *,
                locale: str | None = None,
                **kwargs,
            ):
                self.args = (key, count)
                kwargs["locale"] = locale
                self.kwargs = kwargs

            def __repr__(self):
                return translate(*self.args, **self.kwargs)

        return LazyWrapper

    def get_current_locale(self) -> str:
        """Get the current locale from the request context."""
        return format_locale(current.locale) or self.default_locale

    def get_current_timezone(self) -> datetime.tzinfo:
        return babel_dates.get_timezone(current.timezone) or self.default_timezone

    def negotiate_locale(self, accepted: list[str]) -> str | None:
        """Find the best match between the locales available and the
        ones in the `accepted` list.
        """
        available = self.translations.keys()
        for locale in accepted:
            if locale in available:
                return locale
        return None

    def translate(
        self,
        key: str,
        count: int = 1,
        *,
        locale: str | None = None,
        **kwargs,
    ) -> t.Any:
        """Get the translation for the given key using the current locale.

        If the value is a dictionary, and `count` is defined, uses the value
        whose key is that number. If that key doesn't exist, a `'n'` key
        is tried instead. If that doesn't exits either, an empty string is
        returned.

        The final value is formatted using `kwargs` (and also `count` if
        available) so the format placeholders must be named instead of
        positional.

        If the value isn't a dictionary or a string, is returned as is.

        Arguments:
            key:
                The ID of the looked up translation
            count:
                If the value is a dictionary, and `count` is defined,
                uses the value whose key is that number. If that key doesn't exist,
                a 'n' key is tried instead. If that doesn't exits either, an
                empty string is returned.
            locale:
                must be a :class:`babel.Locale` instance or a string.
            **kwargs:
                Values for string interpolation of the translation.

        Examples:

            >> translate('hello_world')
            'hello {what}'
            >> translate('hello_world', what='Susan')
            'hello Susan'
            >> translate('a_list', what='world')
            ['a', 'b', 'c']
            >> translate({1: 'an apple', 'n': '{count} apples'}, count=1)
            'an apple'
            >> translate({1: 'an apple', 'n': '{count} apples'}, count=2)
            '2 apples'
            >> translate({1: 'an apple', 2: '{count} apples'}, count=42)
            ''

        """
        if not self.translations:
            # i18n support is not installed
            return key

        locale = format_locale(locale) if locale else self.get_current_locale()

        key = str(key)
        value = self._key_lookup(locale, key)
        if value is None:
            return Markup("<missing:{0}/>".format(key))

        if isinstance(value, dict):
            value = self._pluralize(value, locale=locale, count=count)

        if isinstance(value, str):
            kwargs.setdefault("count", count)
            value = value.format(**kwargs)
            return Markup(value)

        return value

    def test_for_incomplete_locales(self, *locales) -> dict[str, set]:
        """Check a list of locales for keys that are defined in one but not in
        the other.

        Arguments:
            locales:
                Two or more locales as strings. If not provided, all
                of the available locales are tested.

        Return:
            A dictionary with string locales as keys and sets of missing
            keys for those locales as values.

        """
        if not locales:
            locales = self.translations.keys()

        locales = [format_locale(locale) for locale in locales]

        all_keys = []
        keys = {}
        for locale in locales:
            trans, *_ = self._get_locale_translations(locale)
            trans_keys = flatten(trans).keys()
            keys[locale] = set(trans_keys)
            all_keys.extend(trans_keys)

        all_keys = set(all_keys)
        missing_keys = {}
        for key, value in keys.items():
            missing = all_keys - value
            if missing:
                missing_keys[key] = missing

        return missing_keys

    # Private

    def _key_lookup(self, locale: str, key: str) -> str | dict | None:
        """Return the value of the translation for the given key using the
        given locale.
        """
        trans_list = self._get_locale_translations(locale)
        value: str | dict | None = None
        for trans in trans_list:
            for subkey in key.split("."):
                value = trans.get(subkey)
                if isinstance(value, dict):
                    trans = value
                else:
                    break
            if value is not None:
                return value

        return None

    def _get_locale_translations(self, locale: str) -> list[dict[str, t.Any]]:
        """Returns the available translations for a locale.

        If the locale has a territory (e.g.: 'es_PE'), the territory-specific
        translations are added first if they exists.

        The general language translations are added into the list in any case,
        if they exists.

        Raises a `TranslationsNotFound` exception if there are no translations for
        the locale or for the general language.
        """
        assert self._translations is not None
        trans = []

        l_trans = self._translations.get(locale)
        if l_trans:
            trans.append(l_trans)

        if "_" in locale:
            language = get_language(locale)
            g_trans = self._translations.get(language)
            if g_trans:
                trans.append(g_trans)

        if not trans:
            raise TranslationsNotFound(locale)

        return trans

    def _pluralize(self, dic: dict, *, locale: str, count: int = 1):
        """Takes a dictionary, a locale, and a number, and return the value
        whose key in the dictionary is either

        a. that number
        b. the value for "zero" if exists and teh number is 0
        c. the textual representation of that number according to the [CLDR
            rules][rules] for the locale, Depending of the language, this can be:
            "zero", "one", "two", "few", "many", or "other".

        [rules]: https://cldr.unicode.org/index/cldr-spec/plural-rules

        Finally, if none of these exits, an empty string is returned.

        Note that this function **does not** interpolate the string, just returns
        the right one for the value of `count`.
        """
        scount = str(count).strip()
        plural = dic.get(count, dic.get(scount))
        if plural is not None:
            return plural

        if count == 0:
            plural = dic.get("zero")
            if plural is not None:
                return plural

        babel_locale = babel.Locale(locale)
        tag = babel_locale.plural_form(count) or "other"
        return dic.get(tag, "")


def get_language(locale: str) -> str:
    return locale.split("_")[0]


def flatten(dic):
    """Flatten a dictionary, separating keys by dots.

    Example:

    >> dic = {
        'a': 1,
        'c': {
            'a': 2,
            'b': {
                'x': 5,
                'y' : 10,
            }
        },
        'd': [1, 2, 3],
    }
    >> flatten(dic)
    {'a': 1, 'c.a': 2, 'c.b.x': 5, 'c.b.y': 10, 'd': [1, 2, 3]}

    """

    def items():
        for key, value in dic.items():
            if isinstance(value, dict):
                for subkey, subvalue in flatten(value).items():
                    yield str(key) + "." + str(subkey), subvalue
            else:
                yield key, value

    return dict(items())
