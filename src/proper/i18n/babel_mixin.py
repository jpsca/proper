import datetime
import decimal
import typing as t
from collections.abc import Sequence

import babel.dates as babel_dates
import babel.lists as babel_lists
import babel.numbers as babel_numbers

from ..helpers import format_locale


class BabelMixin:
    """Mixin class to provide Babel integration for l10n."""

    def get_current_locale(self) -> str:
        return "en"

    def get_current_timezone(self) -> datetime.tzinfo:
        return babel_dates.get_timezone("UTC")

    def format_datetime(
        self,
        datetime: datetime.datetime | None = None,
        format: str = "medium",
        *,
        timezone: str | None = None,
        locale: str | None = None,
    ) -> str:
        """Return a date formatted according to the given pattern.

        >> dt = datetime(2007, 4, 1, 15, 30)
        >> format_datetime(dt, locale='en_US')
        'Apr 1, 2007, 3:30:00\u202fPM'

        If you don't want to use the locale default formats, you can specify a
        custom date pattern:

        >> format_datetime(dt, "yyyy.MM.dd G 'at' HH:mm:ss zzz", timezone='US/Eastern', locale='en')
        '2007.04.01 AD at 11:30:00 EDT'

        Arguments:
            datetime:
                the `datetime` object; if `None`, the current date and time is used.
            format:
                "full", "long", "medium", "short", or a custom date/time pattern.
            timezone:
                force the timezone to use for formatting.
            locale:
                force the locale to use for formatting.

        """
        return babel_dates.format_datetime(
            datetime,
            format=format,
            tzinfo=babel_dates.get_timezone(timezone) if timezone else self.get_current_timezone(),
            locale=format_locale(locale) if locale else self.get_current_locale(),
        )

    def format_date(
        self,
        date: datetime.date | None = None,
        format: str = "medium",
        *,
        locale: str | None = None,
    ) -> str:
        """Return a date formatted according to the given pattern.

        >> d = date(2007, 4, 1)
        >> format_date(d, locale='en_US')
        'Apr 1, 2007'
        >> format_date(d, format='full', locale='de_DE')
        'Sonntag, 1. April 2007'

        If you don't want to use the locale default formats, you can specify a
        custom date pattern:

        >> format_date(d, "EEE, MMM d, ''yy", locale='en')
        "Sun, Apr 1, '07"

        Arguments:
            date:
                the `date` object; if `None`, the current date is used.
            format:
                "full", "long", "medium", "short", or a custom date pattern.
            locale:
                force the locale to use for formatting.

        """
        return babel_dates.format_date(
            date,
            format=format,
            locale=format_locale(locale) if locale else self.get_current_locale(),
        )

    def format_time(
        self,
        time: datetime.time | datetime.datetime | float | None = None,
        format: str = "medium",
        *,
        timezone: str | None = None,
        locale: str | None = None,
    ) -> str:
        """Return a time formatted according to the given pattern.

        >> t = time(15, 30)
        >> format_time(t, locale='en_US')
        '3:30:00\u202fPM'
        >> format_time(t, format='short', locale='de_DE')
        '15:30'

        If you don't want to use the locale default formats, you can specify a
        custom time pattern:

        >> format_time(t, "hh 'o''clock' a", locale='en')
        "03 o'clock PM"

        For any pattern requiring the display of the time-zone a
        timezone has to be specified explicitly:

        >> t = datetime(2007, 4, 1, 15, 30).astimezone(get_timezone('Europe/Paris'))
        >> format_time(t, format='full', timezone='Europe/Paris', locale='fr_FR')
        '15:30:00 heure d’été d’Europe centrale'
        >> format_time(t, "hh 'o''clock' a, zzzz", timezone='US/Eastern', locale='en')
        "09 o'clock AM, Eastern Daylight Time"

        As that example shows, when this function gets passed a
        `datetime.datetime` value, the actual time in the formatted string is
        adjusted to the timezone specified by the `timezone` parameter. If the
        `datetime` is "naive" (i.e. it has no associated timezone information),
        it is assumed to be in UTC.

        These timezone calculations are **not** performed if the value is of type
        `datetime.time`, as without date information there's no way to determine
        what a given time would translate to in a different timezone without
        information about whether daylight savings time is in effect or not. This
        means that time values are left as-is, and the value of the `timezone`
        parameter is only used to display the timezone name if needed:

        >> t = time(15, 30)
        >> format_time(t, format='full', timezone='Europe/Paris', locale='fr_FR')
        '15:30:00 heure normale d\u2019Europe centrale'
        >> format_time(t, format='full', timezone='US/Eastern', locale='en_US')
        '3:30:00\u202fPM Eastern Standard Time'

        Arguments:
            time:
                the `time` or `datetime` object; if `None`, the current
                time in UTC is used.
            format:
                either "full", "long", "medium", or "short", or a custom
                date/time pattern.
            timezone:
                force the timezone to use for formatting.
            locale:
                force the locale to use for formatting.

        """
        return babel_dates.format_time(
            time,
            format=format,
            tzinfo=babel_dates.get_timezone(timezone) if timezone else self.get_current_timezone(),
            locale=format_locale(locale) if locale else self.get_current_locale(),
        )

    def format_timedelta(
        self,
        delta: datetime.timedelta | int,
        *,
        granularity: t.Literal[
            "year",
            "month",
            "week",
            "day",
            "hour",
            "minute",
            "second",
        ] = "second",
        threshold: float = 0.85,
        add_direction: bool = False,
        format: t.Literal["narrow", "short", "long"] = "long",
        locale: str | None = None,
    ) -> str:
        """Return a time delta according to the rules of the given locale.

        >> from datetime import timedelta
        >> format_timedelta(timedelta(weeks=12), locale='en_US')
        '3 months'
        >> format_timedelta(timedelta(seconds=1), locale='es')
        '1 segundo'

        The granularity parameter can be provided to alter the lowest unit
        presented, which defaults to a second.

        >> format_timedelta(timedelta(hours=3), granularity='day', locale='en_US')
        '1 day'

        The threshold parameter can be used to determine at which value the
        presentation switches to the next higher unit. A higher threshold factor
        means the presentation will switch later. For example:

        >> format_timedelta(timedelta(hours=23), threshold=0.9, locale='en_US')
        '1 day'
        >> format_timedelta(timedelta(hours=23), threshold=1.1, locale='en_US')
        '23 hours'

        In addition directional information can be provided that informs
        the user if the date is in the past or in the future:

        >> format_timedelta(timedelta(hours=1), add_direction=True, locale='en')
        'in 1 hour'
        >> format_timedelta(timedelta(hours=-1), add_direction=True, locale='en')
        '1 hour ago'

        The format parameter controls how compact or wide the presentation is:

        >> format_timedelta(timedelta(hours=3), format='short', locale='en')
        '3 hr'
        >> format_timedelta(timedelta(hours=3), format='narrow', locale='en')
        '3h'

        Arguments:
            delta:
                a `timedelta` object representing the time difference to
                format, or the delta in seconds as an `int` value
            granularity:
                determines the smallest unit that should be displayed,
                the value can be either "year", "month", "week", "day",
                "hour", "minute" or "second"
            threshold:
                factor that determines at which point the presentation
                switches to the next higher unit
            add_direction:
                if this flag is set to `True` the return value will include directional
                information. For instance a positive timedelta will include the
                information about it being in the future, a negative will be information
                about the value being in the past.
            format:
                the format, can be "narrow", "short" or "long".
            locale:
                force the locale to use for formatting.
        """
        return babel_dates.format_timedelta(
            delta=delta,
            granularity=granularity,
            threshold=threshold,
            add_direction=add_direction,
            format=format,
            locale=format_locale(locale) if locale else self.get_current_locale(),
        )

    def format_skeleton(
        self,
        datetime: datetime.datetime | None = None,
        skeleton: str = "yMMMd",
        *,
        fuzzy: bool = True,
        timezone: str | None = None,
        locale: str | None = None,
    ) -> str:
        """Return a time and/or date formatted according to the given pattern.

        The skeletons are defined in the CLDR data and provide more flexibility
        than the simple short/long/medium formats, but are a bit harder to use.
        The are defined using the date/time symbols without order or punctuation
        and map to a suitable format for the given locale.

        >> t = datetime(2007, 4, 1, 15, 30)
        >> format_skeleton('MMMEd', t, locale='fr')
        'dim. 1 avr.'

        >> format_skeleton('MMMEd', t, locale='en')
        'Sun, Apr 1'

        >> # yMMd is not in the Finnish locale; yMd gets used
        >> format_skeleton('yMMd', t, locale='fi')
        '1.4.2007'

        >> # yMMd is not in the Finnish locale, an error is thrown
        >> format_skeleton('yMMd', t, fuzzy=False, locale='fi')
        Traceback (most recent call last):
            ...
        KeyError: yMMd

        >> # GH is not in the Finnish locale and there is no close match, an error is thrown
        >> format_skeleton('GH', t, fuzzy=True, locale='fi_FI')
        Traceback (most recent call last):
            ...
        KeyError: None

        After the skeleton is resolved to a pattern `format_datetime` is called so
        all timezone processing etc. is the same as for that.

        Arguments:
            datetime:
                the `datetime` object; if `None`, the current datetime in UTC is used.
            skeleton:
                A date time skeleton as defined in the cldr data.
            fuzzy:
                If the skeleton is not found, allow choosing a skeleton that's close enough to it.
                If there is no close match, a `KeyError` is thrown.
            timezone:
                force the timezone to use for formatting.
            locale:
                force the locale to use for formatting.

        """
        return babel_dates.format_skeleton(
            skeleton=skeleton,
            datetime=datetime,
            fuzzy=fuzzy,
            tzinfo=babel_dates.get_timezone(timezone) if timezone else self.get_current_timezone(),
            locale=format_locale(locale) if locale else self.get_current_locale(),
        )

    def format_interval(
        self,
        start: datetime.date | datetime.time | float,
        end: datetime.date | datetime.time | float,
        skeleton: str | None = None,
        *,
        fuzzy: bool = True,
        timezone: str | None = None,
        locale: str | None = None,
    ) -> str:
        """
        Format an interval between two instants according to the locale's rules.

        >> from datetime import date, time
        >> format_interval(date(2016, 1, 15), date(2016, 1, 17), "yMd", locale="fi")
        '15.–17.1.2016'

        >> format_interval(time(12, 12), time(16, 16), "Hm", locale="en_GB")
        '12:12–16:16'

        >> format_interval(time(5, 12), time(16, 16), "hm", locale="en_US")
        '5:12\u202fAM\u2009–\u20094:16\u202fPM'

        >> format_interval(time(16, 18), time(16, 24), "Hm", locale="it")
        '16:18–16:24'

        If the start instant equals the end instant, the interval is formatted like the instant.

        >> format_interval(time(16, 18), time(16, 18), "Hm", locale="it")
        '16:18'

        Unknown skeletons fall back to "default" formatting.

        >> format_interval(date(2015, 1, 1), date(2017, 1, 1), "wzq", locale="ja")
        '2015/01/01～2017/01/01'

        >> format_interval(time(16, 18), time(16, 24), "xxx", locale="ja")
        '16:18:00～16:24:00'

        >> format_interval(date(2016, 1, 15), date(2016, 1, 17), "xxx", locale="de")
        '15.01.2016\u2009–\u200917.01.2016'

        Arguments:
            start:
                First instant (datetime/date/time)
            end:
                Second instant (datetime/date/time)
            skeleton:
                The "skeleton format" to use for formatting.
            fuzzy:
                If the skeleton is not found, allow choosing a skeleton that's close enough to it.
            timezone:
                force the timezone to use for formatting, if none is already attached.
            locale:
                force the locale to use for formatting.

        """
        return babel_dates.format_interval(
            start=start,
            end=end,
            skeleton=skeleton,
            fuzzy=fuzzy,
            tzinfo=babel_dates.get_timezone(timezone) if timezone else self.get_current_timezone(),
            locale=format_locale(locale) if locale else self.get_current_locale(),
        )

    def format_list(
        self,
        lst: Sequence[str],
        *,
        style: t.Literal[
            "standard",
            "standard-short",
            "or",
            "or-short",
            "unit",
            "unit-short",
            "unit-narrow",
        ] = "standard",
        locale: str | None = None,
    ) -> Sequence[str]:
        """Format the items in `lst` as a list.

        >> format_list(['apples', 'oranges', 'pears'], locale='en')
        'apples, oranges, and pears'
        >> format_list(['apples', 'oranges', 'pears'], locale='zh')
        'apples、oranges和pears'
        >> format_list(['omena', 'peruna', 'aplari'], style='or', locale='fi')
        'omena, peruna tai aplari'

        Not all styles are necessarily available in all locales.
        The function will attempt to fall back to replacement styles according to the rules
        set forth in the CLDR root XML file, and raise a ValueError if no suitable replacement
        can be found.

        The following text is verbatim from the Unicode TR35-49 spec [1].

        * standard:
        A typical 'and' list for arbitrary placeholders.
        eg. "January, February, and March"
        * standard-short:
        A short version of an 'and' list, suitable for use with short or abbreviated placeholder values.
        eg. "Jan., Feb., and Mar."
        * or:
        A typical 'or' list for arbitrary placeholders.
        eg. "January, February, or March"
        * or-short:
        A short version of an 'or' list.
        eg. "Jan., Feb., or Mar."
        * unit:
        A list suitable for wide units.
        eg. "3 feet, 7 inches"
        * unit-short:
        A list suitable for short units
        eg. "3 ft, 7 in"
        * unit-narrow:
        A list suitable for narrow units, where space on the screen is very limited.
        eg. "3′ 7″"

        [1]: https://www.unicode.org/reports/tr35/tr35-49/tr35-general.html#ListPatterns

        Arguments:
            lst:
                a sequence of items to format in to a list
            style:
                the style to format the list with.
            locale:
                force the locale to use for formatting.

        """
        return babel_lists.format_list(
            lst,
            style=style,
            locale=format_locale(locale) if locale else self.get_current_locale(),
        )

    def format_decimal(
        self,
        number: float | decimal.Decimal | str,
        *,
        decimal_quantization: bool = True,
        group_separator: bool = True,
        numbering_system: str = "latn",
        locale: str | None = None,
    ) -> str:
        """Return the given decimal number formatted for a specific locale.

        >> format_decimal(1.2345, locale='en_US')
        '1.234'
        >> format_decimal(1.2346, locale='en_US')
        '1.235'
        >> format_decimal(-1.2346, locale='en_US')
        '-1.235'
        >> format_decimal(1.2345, locale='sv_SE')
        '1,234'
        >> format_decimal(1.2345, locale='de')
        '1,234'
        >> format_decimal(1.2345, locale='ar_EG', numbering_system='default')
        '1٫234'
        >> format_decimal(1.2345, locale='ar_EG', numbering_system='latn')
        '1.234'

        The appropriate thousands grouping and the decimal separator are used for
        each locale:

        >> format_decimal(12345.5, locale='en_US')
        '12,345.5'

        By default the locale is allowed to truncate and round a high-precision
        number by forcing its format pattern onto the decimal part. You can bypass
        this behavior with the `decimal_quantization` parameter:

        >> format_decimal(1.2346, locale='en_US')
        '1.235'
        >> format_decimal(1.2346, locale='en_US', decimal_quantization=False)
        '1.2346'
        >> format_decimal(12345.67, locale='fr_CA', group_separator=False)
        '12345,67'
        >> format_decimal(12345.67, locale='en_US', group_separator=True)
        '12,345.67'

        Arguments:
            number:
                the number to format.
            decimal_quantization:
                Truncate and round high-precision numbers to the format pattern. Defaults to `True`.
            group_separator:
                Boolean to switch group separator on/off in a locale's number format.
            numbering_system:
                The numbering system used for formatting number symbols. Defaults to "latn".
                The special value "default" will use the default numbering system of the locale.
            locale:
                force the locale to use for formatting.

        Raises:
            `UnsupportedNumberingSystemError`: If the numbering system is not supported by the locale.

        """
        return babel_numbers.format_decimal(
            number,
            decimal_quantization=decimal_quantization,
            group_separator=group_separator,
            numbering_system=numbering_system,
            locale=format_locale(locale) if locale else self.get_current_locale(),
        )

    def format_compact_decimal(
        self,
        number: float | decimal.Decimal | str,
        *,
        format_type: t.Literal["short", "long"] = "short",
        fraction_digits: int = 0,
        numbering_system: str = "latn",
        locale: str | None = None,
    ) -> str:
        """Return the given decimal number formatted for a specific locale in compact form.

        >> format_compact_decimal(12345, format_type="short", locale='en_US')
        '12K'
        >> format_compact_decimal(12345, format_type="long", locale='en_US')
        '12 thousand'
        >> format_compact_decimal(12345, format_type="short", locale='en_US', fraction_digits=2)
        '12.34K'
        >> format_compact_decimal(1234567, format_type="short", locale="ja_JP")
        '123万'
        >> format_compact_decimal(2345678, format_type="long", locale="mk")
        '2 милиони'
        >> format_compact_decimal(21000000, format_type="long", locale="mk")
        '21 милион'
        >> format_compact_decimal(12345, format_type="short", locale='ar_EG', fraction_digits=2, numbering_system='default')
        '12٫34\xa0ألف'

        Arguments:
            number:
                the number to format.
            format_type:
                Compact format to use ("short" or "long").
            fraction_digits:
                Number of digits after the decimal point to use. Defaults to `0`.
            numbering_system:
                The numbering system used for formatting number symbols. Defaults to "latn".
                The special value "default" will use the default numbering system of the locale.
            locale:
                force the locale to use for formatting.

        Raises:
            `UnsupportedNumberingSystemError`: If the numbering system is not supported by the locale.
        """
        return babel_numbers.format_compact_decimal(
            number,
            format_type=format_type,
            fraction_digits=fraction_digits,
            numbering_system=numbering_system,
            locale=format_locale(locale) if locale else self.get_current_locale(),
        )

    def format_currency(
        self,
        number: float | decimal.Decimal | str,
        currency: str,
        *,
        format: str | None = None,
        currency_digits: bool = True,
        format_type: t.Literal["name", "standard", "accounting"] = "standard",
        decimal_quantization: bool = True,
        group_separator: bool = True,
        numbering_system: str = "latn",
        locale: str | None = None,
    ) -> str:
        """Return formatted currency value.

        >> format_currency(1099.98, 'USD', locale='en_US')
        '$1,099.98'
        >> format_currency(1099.98, 'USD', locale='es_CO')
        'US$1.099,98'
        >> format_currency(1099.98, 'EUR', locale='de_DE')
        '1.099,98\xa0\u20ac'
        >> format_currency(1099.98, 'EGP', locale='ar_EG', numbering_system='default')
        '\u200f1٬099٫98\xa0ج.م.\u200f'

        The format can also be specified explicitly.  The currency is
        placed with the '¤' sign.  As the sign gets repeated the format
        expands (¤ being the symbol, ¤¤ is the currency abbreviation and
        ¤¤¤ is the full name of the currency):

        >> format_currency(1099.98, 'EUR', format='\xa4\xa4 #,##0.00', locale='en_US')
        'EUR 1,099.98'
        >> format_currency(1099.98, 'EUR', format='#,##0.00 \xa4\xa4\xa4', locale='en_US')
        '1,099.98 euros'

        Currencies usually have a specific number of decimal digits. This function
        favours that information over the given format:

        >> format_currency(1099.98, 'JPY', locale='en_US')
        '\xa51,100'
        >> format_currency(1099.98, 'COP', format='#,##0.00', locale='es_ES')
        '1.099,98'

        However, the number of decimal digits can be overridden from the currency
        information, by setting the last parameter to ``False``:

        >> format_currency(1099.98, 'JPY', locale='en_US', currency_digits=False)
        '\xa51,099.98'
        >> format_currency(1099.98, 'COP', format='#,##0.00', locale='es_ES', currency_digits=False)
        '1.099,98'

        If a format is not specified the type of currency format to use
        from the locale can be specified:

        >> format_currency(1099.98, 'EUR', locale='en_US', format_type='standard')
        '\u20ac1,099.98'

        When the given currency format type is not available, an exception is
        raised:

        >> format_currency('1099.98', 'EUR', locale='root', format_type='unknown')
        Traceback (most recent call last):
            ...
        UnknownCurrencyFormatError: "'unknown' is not a known currency format type"

        >> format_currency(101299.98, 'USD', locale='en_US', group_separator=False)
        '$101299.98'

        >> format_currency(101299.98, 'USD', locale='en_US', group_separator=True)
        '$101,299.98'

        You can also pass format_type='name' to use long display names. The order of
        the number and currency name, along with the correct localized plural form
        of the currency name, is chosen according to locale:

        >> format_currency(1, 'USD', locale='en_US', format_type='name')
        '1.00 US dollar'
        >> format_currency(1099.98, 'USD', locale='en_US', format_type='name')
        '1,099.98 US dollars'
        >> format_currency(1099.98, 'USD', locale='ee', format_type='name')
        'us ga dollar 1,099.98'

        By default the locale is allowed to truncate and round a high-precision
        number by forcing its format pattern onto the decimal part. You can bypass
        this behavior with the `decimal_quantization` parameter:

        >> format_currency(1099.9876, 'USD', locale='en_US')
        '$1,099.99'
        >> format_currency(1099.9876, 'USD', locale='en_US', decimal_quantization=False)
        '$1,099.9876'

        Arguments:
            number:
                the number to format.
            currency:
                the currency code.
            format:
                the format string to use.
            format_type:
                The currency format type to use
            currency_digits:
                use the currency's natural number of decimal digits or not. Defaults to `True`.
            decimal_quantization:
                Truncate and round high-precision numbers to the format pattern. Defaults to `True`.
            group_separator:
                Boolean to switch group separator on/off in a locale's number format.
            numbering_system:
                The numbering system used for formatting number symbols. Defaults to "latn".
                The special value "default" will use the default numbering system of the locale.
            locale:
                force the locale to use for formatting.

        Raises:
            `UnsupportedNumberingSystemError`: If the numbering system is not supported by the locale.
        """
        return babel_numbers.format_currency(
            number=number,
            currency=currency,
            format=format,
            format_type=format_type,
            currency_digits=currency_digits,
            decimal_quantization=decimal_quantization,
            group_separator=group_separator,
            numbering_system=numbering_system,
            locale=format_locale(locale) if locale else self.get_current_locale(),
        )

    def format_compact_currency(
        self,
        number: float | decimal.Decimal | str,
        currency: str,
        *,
        fraction_digits: int = 0,
        numbering_system: str = "latn",
        locale: str | None = None,
    ) -> str:
        """Format a number as a currency value in compact form.

        >> format_compact_currency(12345, 'USD', locale='en_US')
        '$12K'
        >> format_compact_currency(123456789, 'USD', locale='en_US', fraction_digits=2)
        '$123.46M'
        >> format_compact_currency(123456789, 'EUR', locale='de_DE', fraction_digits=1)
        '123,5\xa0Mio.\xa0€'

        Arguments:
            number:
                The number to format.
            currency:
                The currency code.
            fraction_digits:
                Number of digits after the decimal point to use. Defaults to `0`.
            numbering_system:
                The numbering system used for formatting number symbols. Defaults to "latn".
                The special value "default" will use the default numbering system of the locale.
            locale:
                force the locale to use for formatting.

        Raises:
            `UnsupportedNumberingSystemError`: If the numbering system is not supported by the locale.

        """
        return babel_numbers.format_compact_currency(
            number=number,
            currency=currency,
            fraction_digits=fraction_digits,
            numbering_system=numbering_system,
            locale=format_locale(locale) if locale else self.get_current_locale(),
        )

    def format_percent(
        self,
        number: float | decimal.Decimal | str,
        *,
        format: str | None = None,
        decimal_quantization: bool = True,
        group_separator: bool = True,
        numbering_system: str = "latn",
        locale: str | None = None,
    ) -> str:
        """Return formatted percent value for a specific locale.

        >> format_percent(0.34, locale='en_US')
        '34%'
        >> format_percent(25.1234, locale='en_US')
        '2,512%'
        >> format_percent(25.1234, locale='sv_SE')
        '2\xa0512\xa0%'
        >> format_percent(25.1234, locale='ar_EG', numbering_system='default')
        '2٬512%'

        The format pattern can also be specified explicitly:

        >> format_percent(25.1234, format='#,##0\u2030', locale='en_US')
        '25,123‰'

        By default the locale is allowed to truncate and round a high-precision
        number by forcing its format pattern onto the decimal part. You can bypass
        this behavior with the `decimal_quantization` parameter:

        >> format_percent(23.9876, locale='en_US')
        '2,399%'
        >> format_percent(23.9876, locale='en_US', decimal_quantization=False)
        '2,398.76%'

        >> format_percent(229291.1234, locale='pt_BR', group_separator=False)
        '22929112%'

        >> format_percent(229291.1234, locale='pt_BR', group_separator=True)
        '22.929.112%'

        Arguments:
            number:
                the percent number to format.
            format:
                the format string to use.
            decimal_quantization:
                Truncate and round high-precision numbers to the format pattern. Defaults to `True`.
            group_separator:
                Boolean to switch group separator on/off in a locale's number format.
            numbering_system:
                The numbering system used for formatting number symbols. Defaults to "latn".
                The special value "default" will use the default numbering system of the locale.
            locale:
                force the locale to use for formatting.

        Raises:
            `UnsupportedNumberingSystemError`: If the numbering system is not supported by the locale.

        """
        return babel_numbers.format_percent(
            number=number,
            format=format,
            decimal_quantization=decimal_quantization,
            group_separator=group_separator,
            numbering_system=numbering_system,
            locale=format_locale(locale) if locale else self.get_current_locale(),
        )

    def format_scientific(
        self,
        number: float | decimal.Decimal | str,
        *,
        format: str | None = None,
        decimal_quantization: bool = True,
        numbering_system: str = "latn",
        locale: str | None = None,
    ) -> str:
        """Return value formatted in scientific notation for a specific locale.

        >> format_scientific(10000, locale='en_US')
        '1E4'
        >> format_scientific(10000, locale='ar_EG', numbering_system='default')
        '1أس4'

        The format pattern can also be specified explicitly:

        >> format_scientific(1234567, format='##0.##E00', locale='en_US')
        '1.23E06'

        By default the locale is allowed to truncate and round a high-precision
        number by forcing its format pattern onto the decimal part. You can bypass
        this behavior with the `decimal_quantization` parameter:

        >> format_scientific(1234.9876, format='#.##E0', locale='en_US')
        '1.23E3'
        >> format_scientific(1234.9876, format='#.##E0', locale='en_US', decimal_quantization=False)
        '1.2349876E3'

        Arguments:
            number:
                the percent number to format.
            format:
                the format string to use.
            decimal_quantization:
                Truncate and round high-precision numbers to the format pattern. Defaults to `True`.
            numbering_system:
                The numbering system used for formatting number symbols. Defaults to "latn".
                The special value "default" will use the default numbering system of the locale.
            locale:
                force the locale to use for formatting.

        Raises:
            `UnsupportedNumberingSystemError`: If the numbering system is not supported by the locale.

        """
        return babel_numbers.format_scientific(
            number=number,
            format=format,
            decimal_quantization=decimal_quantization,
            numbering_system=numbering_system,
            locale=format_locale(locale) if locale else self.get_current_locale(),
        )

    def get_day_names(
        self,
        width: t.Literal["wide", "abbreviated", "short", "narrow"] = "wide",
        *,
        context: t.Literal["format", "stand-alone"] = "format",
        locale: str | None = None,
    ) -> list[str]:
        """Return the day names used by the locale for the specified format.

        >> get_day_names('wide', locale='en_US')[1]
        'Tuesday'
        >> get_day_names('short', locale='en_US')[1]
        'Tu'
        >> get_day_names('abbreviated', locale='es')[1]
        'mar'
        >> get_day_names('narrow', context='stand-alone', locale='de_DE')[1]
        'D'

        Arguments:
            width:
                the width to use, either "wide", "abbreviated", "short" or "narrow".
            context:
                the context, either "format" or "stand-alone".
            locale:
                force the locale to use for formatting.

        """
        return list(
            babel_dates.get_day_names(
                width=width,
                context=context,
                locale=format_locale(locale) if locale else self.get_current_locale(),
            )
        )

    def get_month_names(
        self,
        width: t.Literal["wide", "abbreviated", "narrow"] = "wide",
        *,
        context: t.Literal["format", "stand-alone"] = "format",
        locale: str | None = None,
    ) -> list[str]:
        """Return the month names used by the locale for the specified format.

        >> get_month_names('wide', locale='en_US')[1]
        'January'
        >> get_month_names('abbreviated', locale='es')[1]
        'ene'
        >> get_month_names('narrow', context='stand-alone', locale='de_DE')[1]
        'J'

        Arguments:
            width:
                the width to use, either "wide", "abbreviated", or "narrow".
            context:
                the context, either "format" or "stand-alone".
            locale:
                force the locale to use for formatting.

        """
        return list(
            babel_dates.get_month_names(
                width=width,
                context=context,
                locale=format_locale(locale) if locale else self.get_current_locale(),
            )
        )

    def get_quarter_names(
        self,
        width: t.Literal["wide", "abbreviated", "narrow"] = "wide",
        *,
        context: t.Literal["format", "stand-alone"] = "format",
        locale: str | None = None,
    ) -> list[str]:
        """Return the quarter names used by the locale for the specified format.

        >> get_quarter_names('wide', locale='en_US')[1]
        '1st quarter'
        >> get_quarter_names('abbreviated', locale='de_DE')[1]
        'Q1'
        >> get_quarter_names('narrow', locale='de_DE')[1]
        '1'

        Arguments:
            width:
                the width to use, either "wide", "abbreviated", or "narrow".
            context:
                the context, either "format" or "stand-alone".
            locale:
                force the locale to use for formatting.

        """
        return list(
            babel_dates.get_quarter_names(
                width=width,
                context=context,
                locale=format_locale(locale) if locale else self.get_current_locale(),
            )
        )

    def get_era_names(
        self,
        width: t.Literal["wide", "abbreviated", "narrow"] = "wide",
        *,
        locale: str | None = None,
    ) -> list[str]:
        """Return the era names used by the locale for the specified format.

        >> get_era_names('wide', locale='en_US')[1]
        'Anno Domini'
        >> get_era_names('abbreviated', locale='de_DE')[1]
        'n. Chr.'


        Arguments:
            width:
                the width to use, either "wide", "abbreviated", or "narrow".
            locale:
                force the locale to use for formatting.

        """
        return list(
            babel_dates.get_era_names(
                width=width,
                locale=format_locale(locale) if locale else self.get_current_locale(),
            )
        )

    def get_currency_name(
        self,
        currency: str,
        *,
        count: float | decimal.Decimal | None = None,
        locale: str | None = None,
    ) -> str:
        """Return the name of the currency used by the locale.

        >> get_currency_name('USD', locale='en_US')
        'US Dollar'
        >> get_currency_name('EUR', locale='de_DE')
        'Euro'

        Arguments:
            currency:
                the currency code to get the name for.
            count:
                an optional count. The currency name will be pluralized to that number if possible.
            locale:
                force the locale to use for formatting.

        """
        return babel_numbers.get_currency_name(
            currency=currency,
            count=count,
            locale=format_locale(locale) if locale else self.get_current_locale(),
        )

    def get_currency_symbol(
        self,
        currency: str,
        *,
        locale: str | None = None,
    ) -> str:
        """Return the symbol of the currency used by the locale.

        >> get_currency_symbol('USD', locale='en_US')
        '$'
        >> get_currency_symbol('EUR', locale='de_DE')
        '€'

        Arguments:
            currency:
                the currency code to get the symbol for.
            locale:
                force the locale to use for formatting.

        """
        return babel_numbers.get_currency_symbol(
            currency=currency,
            locale=format_locale(locale) if locale else self.get_current_locale(),
        )
