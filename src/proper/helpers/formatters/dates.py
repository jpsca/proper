import datetime
import typing as t
from datetime import tzinfo

import babel.dates as babel_dates

from .http import format_locale


def format_date(
    date: datetime.date | None = None,
    format: str = "medium",
    *,
    timezone: str | tzinfo | None = None,
    locale: str = "en",
) -> str:
    """Formats a date/datetime according to the current locale and timezone.

    ```python
    format_date(date(2007, 4, 1), locale='en_US')
    # => 'Apr 1, 2007'

    format_date(datetime(2007, 4, 1, 15, 30), locale='en_US')
    # => 'Apr 1, 2007, 3:30:00\u202fPM'
    ```

    You can also specify a custom date pattern:

    ```python
    format_date(date(2007, 4, 1), "EEE, MMM d, ''yy", locale='en')
    # => "Sun, Apr 1, '07"

    format_date(
        datetime(2007, 4, 1, 15, 30),
        "yyyy.MM.dd G 'at' HH:mm:ss zzz",
        timezone='US/Eastern',
        locale='en'
    )
    # => '2007.04.01 AD at 11:30:00 EDT'
    ```

    Arguments:
        date:
            The `date` or `datetime` object; if `None`, the current datetime
            is used.
        format:
            "full", "long", "medium", "short", or a custom date/time pattern.
        timezone:
            Force the timezone to use for formatting.
        locale:
            Force the locale to use for formatting.

    """
    date = date or datetime.datetime.now().astimezone(datetime.timezone.utc)

    if isinstance(date, datetime.datetime):
        return babel_dates.format_datetime(
            date,
            format=format,
            tzinfo=babel_dates.get_timezone(timezone) if timezone else None,
            locale=format_locale(locale) if locale else None,
        )
    else:
        return babel_dates.format_date(
            date,
            format=format,
            locale=format_locale(locale) if locale else None,
        )


def format_time(
    time: datetime.time | datetime.datetime | float | None = None,
    format: str = "medium",
    *,
    timezone: str | tzinfo | None = None,
    locale: str = "en",
) -> str:
    """Formats a time according to the current locale and timezone.

    ```python
    t =

    format_time(time(15, 30), locale='en_US')
    # => '3:30:00\u202fPM'

    format_time(time(15, 30), format='short', locale='de_DE')
    # => '15:30'
    ```

    You can also specify a custom time pattern:

    ```python
    format_time(time(15, 30), "hh 'o''clock' a", locale='en')
    # => "03 o'clock PM"
    ```

    For any pattern requiring the display of the time-zone a
    timezone has to be specified explicitly:

    ```python
    dt = datetime(2007, 4, 1, 15, 30).astimezone(get_timezone('Europe/Paris'))

    format_time(dt, format='full', timezone='Europe/Paris', locale='fr_FR')
    # => '15:30:00 heure d’été d’Europe centrale'

    format_time(
        dt, "hh 'o''clock' a, zzzz",
        timezone='US/Eastern',
        locale='en'
    )
    # => "09 o'clock AM, Eastern Daylight Time"
    ```

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

    ```python
    format_time(
        time(15, 30),
        format='full',
        timezone='Europe/Paris',
        locale='fr_FR'
    )
    # => '15:30:00 heure normale d\u2019Europe centrale'

    format_time(
        time(15, 30),
        format='full',
        timezone='US/Eastern',
        locale='en_US'
    )
    # => '3:30:00\u202fPM Eastern Standard Time'
    ```

    Arguments:
        time:
            The `time` or `datetime` object; if `None`, the current
            time in UTC is used.
        format:
            Either "full", "long", "medium", or "short", or a custom
            date/time pattern.
        timezone:
            Force the timezone to use for formatting.
        locale:
            Force the locale to use for formatting.

    """
    return babel_dates.format_time(
        time,
        format=format,
        tzinfo=babel_dates.get_timezone(timezone) if timezone else None,
        locale=format_locale(locale) if locale else None,
    )


def format_timedelta(
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
    locale: str = "en",
) -> str:
    """Formats a timedelta according to the rules of the given locale.

    ```python
    format_timedelta(timedelta(weeks=12), locale='en_US')
    # => '3 months'

    format_timedelta(timedelta(seconds=1), locale='es')
    # => '1 segundo'
    ```

    The granularity parameter can be provided to alter the lowest unit
    presented, which defaults to a second.

    ```python
    format_timedelta(timedelta(hours=3), granularity='day', locale='en_US')
    # => '1 day'
    ```

    The threshold parameter can be used to determine at which value the
    presentation switches to the next higher unit. A higher threshold factor
    means the presentation will switch later. For example:

    ```python
    format_timedelta(timedelta(hours=23), threshold=0.9, locale='en_US')
    # => '1 day'

    format_timedelta(timedelta(hours=23), threshold=1.1, locale='en_US')
    # => '23 hours'
    ```

    In addition directional information can be provided that informs
    the user if the date is in the past or in the future:

    ```python
    format_timedelta(timedelta(hours=1), add_direction=True, locale='en')
    # => 'in 1 hour'

    format_timedelta(timedelta(hours=-1), add_direction=True, locale='en')
    # => '1 hour ago'
    ```

    The format parameter controls how compact or wide the presentation is:

    ```python
    format_timedelta(timedelta(hours=3), format='short', locale='en')
    # => '3 hr'

    format_timedelta(timedelta(hours=3), format='narrow', locale='en')
    # => '3h'
    ```

    Arguments:
        delta:
            A `timedelta` object representing the time difference to
            format, or the delta in seconds as an `int` value
        granularity:
            Determines the smallest unit that should be displayed,
            the value can be either "year", "month", "week", "day",
            "hour", "minute" or "second"
        threshold:
            Factor that determines at which point the presentation
            switches to the next higher unit
        add_direction:
            If this flag is set to `True`, a positive timedelta will mean
            the future (eg. `in 1 hour`) and a negative timedelta the past
            (eg. `1 hour ago`).
        format:
            Can be "narrow", "short" or "long".
        locale:
            Force the locale to use for formatting.
    """
    return babel_dates.format_timedelta(
        delta=delta,
        granularity=granularity,
        threshold=threshold,
        add_direction=add_direction,
        format=format,
        locale=format_locale(locale) if locale else None,
    )


def format_skeleton(
    datetime: datetime.datetime | None = None,
    skeleton: str = "yMMMd",
    *,
    fuzzy: bool = True,
    timezone: str | tzinfo | None = None,
    locale: str = "en",
) -> str:
    """Formats a datetime according to the given pattern, timezone and locale rules.

    The skeletons are defined in the CLDR data and provide more flexibility
    than the simple short/long/medium formats, but are a bit harder to use.
    The are defined using the date/time symbols without order or punctuation
    and map to a suitable format for the given locale.

    ```python
    t = datetime(2007, 4, 1, 15, 30)

    format_skeleton(t, 'MMMEd', locale='fr')
    # => 'dim. 1 avr.'

    format_skeleton(t, 'MMMEd', locale='en')
    # => 'Sun, Apr 1'

    # yMMd is not in the Finnish locale; yMd gets used
    format_skeleton(t, 'yMMd', locale='fi')
    # => '1.4.2007'

    # yMMd is not in the Finnish locale, an error is thrown
    format_skeleton(t, 'yMMd', fuzzy=False, locale='fi')
    Traceback (most recent call last):
        ...
    KeyError: yMMd

    # GH is not in the Finnish locale and there is no close match,
    # an error is thrown
    format_skeleton(t, 'GH', fuzzy=True, locale='fi_FI')
    Traceback (most recent call last):
        ...
    KeyError: None
    ```

    Arguments:
        datetime:
            The `datetime` object; if `None`, the current datetime in UTC is used.
        skeleton:
            A date time skeleton as defined in the cldr data.
        fuzzy:
            If the skeleton is not found, allow choosing a skeleton that's close
            enough to it. If there is no close match, a `KeyError` is thrown.
        timezone:
            Force the timezone to use for formatting.
        locale:
            Force the locale to use for formatting.

    """
    return babel_dates.format_skeleton(
        datetime=datetime,
        skeleton=skeleton,
        fuzzy=fuzzy,
        tzinfo=babel_dates.get_timezone(timezone) if timezone else None,
        locale=format_locale(locale) if locale else None,
    )


def format_interval(
    start: datetime.date | datetime.time | float,
    end: datetime.date | datetime.time | float,
    skeleton: str | None = None,
    *,
    fuzzy: bool = True,
    timezone: str | tzinfo | None = None,
    locale: str = "en",
) -> str:
    """Formats an interval between two dates or times according to the timezone
    and locale's rules.

    ```python
    format_interval(time(5, 12), time(16, 24), "Hm", locale="en_GB")
    # => '5:12–16:24'

    format_interval(time(5, 12), time(16, 24), "hm", locale="en_US")
    # => '5:12\u202fAM\u2009–\u20094:24\u202fPM'

    format_interval(date(2016, 1, 15), date(2016, 1, 17), "yMd", locale="fi")
    # => '15.–17.1.2016'
    ```

    If the start instant equals the end instant, the interval is formatted like
    the instant.

    ```python
    format_interval(time(16, 18), time(16, 18), "Hm", locale="it")
    # => '16:18'
    ```

    Unknown skeletons fall back to "default" formatting.

    ```python
    format_interval(date(2015, 1, 1), date(2017, 1, 1), "wzq", locale="ja")
    # => '2015/01/01～2017/01/01'

    format_interval(date(2016, 1, 15), date(2016, 1, 17), "xxx", locale="de")
    # => '15.01.2016\u2009–\u200917.01.2016'
    ```

    Arguments:
        start:
            First instant (datetime/date/time)
        end:
            Second instant (datetime/date/time)
        skeleton:
            The "skeleton format" to use for formatting.
        fuzzy:
            If the skeleton is not found, allow choosing a skeleton that's close
            enough to it.
        timezone:
            Force the timezone to use for formatting, if none is already attached.
        locale:
            Force the locale to use for formatting.

    """
    return babel_dates.format_interval(
        start=start,
        end=end,
        skeleton=skeleton,
        fuzzy=fuzzy,
        tzinfo=babel_dates.get_timezone(timezone) if timezone else None,
        locale=format_locale(locale) if locale else None,
    )

