import datetime
import decimal
import typing as t
from collections.abc import Sequence
from functools import wraps

import babel.dates as babel_dates
import babel.numbers as babel_numbers

from ..helpers.formatters import (
    format_compact_currency,
    format_compact_decimal,
    format_currency,
    format_date,
    format_decimal,
    format_interval,
    format_list,
    format_percent,
    format_scientific,
    format_size,
    format_skeleton,
    format_time,
    format_timedelta,
)


class Formatters:
    """Mixin class to provide format functions using Babel
    for localization."""

    def get_current_locale(self) -> str:
        return "en"

    def get_current_timezone(self) -> datetime.tzinfo:
        return babel_dates.get_timezone("UTC")

    def get_day_names(
        self,
        width: t.Literal["wide", "abbreviated", "short", "narrow"] = "wide",
        *,
        context: t.Literal["format", "stand-alone"] = "format",
        locale: str | None = None,
    ) -> list[str]:
        """Return the day names used by the locale for the specified format.

        ```python
        get_day_names('wide', locale='en_US')[1]
        # => 'Tuesday'

        get_day_names('short', locale='en_US')[1]
        # => 'Tu'

        get_day_names('abbreviated', locale='es')[1]
        # => 'mar'

        get_day_names('narrow', context='stand-alone', locale='de_DE')[1]
        # => 'D'
        ```

        Arguments:
            width:
                the width to use, either "wide", "abbreviated", "short" or "narrow".
            context:
                the context, either "format" or "stand-alone".
            locale:
                force the locale to use for formatting.

        """
        return t.cast(list[str], list(
            babel_dates.get_day_names(
                width=width,
                context=context,
                locale=locale if locale else self.get_current_locale(),
            )
        ))

    def get_month_names(
        self,
        width: t.Literal["wide", "abbreviated", "narrow"] = "wide",
        *,
        context: t.Literal["format", "stand-alone"] = "format",
        locale: str | None = None,
    ) -> list[str]:
        """Return the month names used by the locale for the specified format.

        ```python
        get_month_names('wide', locale='en_US')[1]
        # => 'January'

        get_month_names('abbreviated', locale='es')[1]
        # => 'ene'

        get_month_names('narrow', context='stand-alone', locale='de_DE')[1]
        # => 'J'
        ```

        Arguments:
            width:
                the width to use, either "wide", "abbreviated", or "narrow".
            context:
                the context, either "format" or "stand-alone".
            locale:
                force the locale to use for formatting.

        """
        return t.cast(list[str], list(
            babel_dates.get_month_names(
                width=width,
                context=context,
                locale=locale if locale else self.get_current_locale(),
            )
        ))

    def get_quarter_names(
        self,
        width: t.Literal["wide", "abbreviated", "narrow"] = "wide",
        *,
        context: t.Literal["format", "stand-alone"] = "format",
        locale: str | None = None,
    ) -> list[str]:
        """Return the quarter names used by the locale for the specified format.

        ```python
        get_quarter_names('wide', locale='en_US')[1]
        # => '1st quarter'

        get_quarter_names('abbreviated', locale='de_DE')[1]
        # => 'Q1'

        get_quarter_names('narrow', locale='de_DE')[1]
        # => '1'
        ```

        Arguments:
            width:
                the width to use, either "wide", "abbreviated", or "narrow".
            context:
                the context, either "format" or "stand-alone".
            locale:
                force the locale to use for formatting.

        """
        return t.cast(list[str], list(
            babel_dates.get_quarter_names(
                width=width,
                context=context,
                locale=locale if locale else self.get_current_locale(),
            )
        ))

    def get_era_names(
        self,
        width: t.Literal["wide", "abbreviated", "narrow"] = "wide",
        *,
        locale: str | None = None,
    ) -> list[str]:
        """Return the era names used by the locale for the specified format.

        ```python
        get_era_names('wide', locale='en_US')[1]
        # => 'Anno Domini'

        get_era_names('abbreviated', locale='de_DE')[1]
        # => 'n. Chr.'
        ```

        Arguments:
            width:
                the width to use, either "wide", "abbreviated", or "narrow".
            locale:
                force the locale to use for formatting.

        """
        return t.cast(list[str], list(
            babel_dates.get_era_names(
                width=width,
                locale=locale if locale else self.get_current_locale(),
            )
        ))

    def get_currency_name(
        self,
        currency: str,
        *,
        count: float | decimal.Decimal | None = None,
        locale: str | None = None,
    ) -> str:
        """Return the name of the currency used by the locale.

        ```python
        get_currency_name('USD', locale='en_US')
        # => 'US Dollar'

        get_currency_name('EUR', locale='de_DE')
        # => 'Euro'
        ```

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
            locale=locale if locale else self.get_current_locale(),
        )

    def get_currency_symbol(
        self,
        currency: str,
        *,
        locale: str | None = None,
    ) -> str:
        """Return the symbol of the currency used by the locale.

        ```python
        get_currency_symbol('USD', locale='en_US')
        # => '$'

        get_currency_symbol('EUR', locale='de_DE')
        # => '€'
        ```

        Arguments:
            currency:
                the currency code to get the symbol for.
            locale:
                force the locale to use for formatting.

        """
        return babel_numbers.get_currency_symbol(
            currency=currency,
            locale=locale if locale else self.get_current_locale(),
        )

    @wraps(format_date)
    def format_date(
        self,
        date: datetime.date | datetime.datetime | None = None,
        format: str = "medium",
        *,
        timezone: str | None = None,
        locale: str | None = None,
    ) -> str:
        return format_date(
            date,
            format=format,
            timezone=timezone if timezone else self.get_current_timezone(),
            locale=locale if locale else self.get_current_locale(),
        )

    @wraps(format_time)
    def format_time(
        self,
        time: datetime.time | datetime.datetime | float | None = None,
        format: str = "medium",
        *,
        timezone: str | None = None,
        locale: str | None = None,
    ) -> str:
        return format_time(
            time,
            format=format,
            timezone=timezone if timezone else self.get_current_timezone(),
            locale=locale if locale else self.get_current_locale(),
        )

    @wraps(format_timedelta)
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
        return format_timedelta(
            delta=delta,
            granularity=granularity,
            threshold=threshold,
            add_direction=add_direction,
            format=format,
            locale=locale if locale else self.get_current_locale(),
        )

    @wraps(format_skeleton)
    def format_skeleton(
        self,
        datetime: datetime.datetime | None = None,
        skeleton: str = "yMMMd",
        *,
        fuzzy: bool = True,
        timezone: str | None = None,
        locale: str | None = None,
    ) -> str:
        return format_skeleton(
            skeleton=skeleton,
            datetime=datetime,
            fuzzy=fuzzy,
            timezone=timezone if timezone else self.get_current_timezone(),
            locale=locale if locale else self.get_current_locale(),
        )

    @wraps(format_interval)
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
        return format_interval(
            start=start,
            end=end,
            skeleton=skeleton,
            fuzzy=fuzzy,
            timezone=timezone if timezone else self.get_current_timezone(),
            locale=locale if locale else self.get_current_locale(),
        )

    @wraps(format_list)
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
        return format_list(
            lst,
            style=style,
            locale=locale if locale else self.get_current_locale(),
        )

    @wraps(format_size)
    def format_size(
        self,
        number: str | int | float | decimal.Decimal | None,
        precision: int = 3,
        significant: bool = True,
        strip_zeros: bool = True,
        round_mode: str = "default",
        locale: str | None = None,
    ) -> str:
        return format_size(
            number=number,
            precision=precision,
            significant=significant,
            strip_zeros=strip_zeros,
            round_mode=round_mode,
            locale=locale if locale else self.get_current_locale(),
        )

    @wraps(format_decimal)
    def format_decimal(
        self,
        number: float | decimal.Decimal | str,
        *,
        quantization: bool = True,
        group_separator: bool = True,
        numbering_system: str = "latn",
        locale: str | None = None,
    ) -> str:
        return format_decimal(
            number,
            quantization=quantization,
            group_separator=group_separator,
            numbering_system=numbering_system,
            locale=locale if locale else self.get_current_locale(),
        )

    @wraps(format_compact_decimal)
    def format_compact_decimal(
        self,
        number: float | decimal.Decimal | str,
        *,
        format_type: t.Literal["short", "long"] = "short",
        fraction_digits: int = 0,
        numbering_system: str = "latn",
        locale: str | None = None,
    ) -> str:
        return format_compact_decimal(
            number,
            format_type=format_type,
            fraction_digits=fraction_digits,
            numbering_system=numbering_system,
            locale=locale if locale else self.get_current_locale(),
        )

    @wraps(format_currency)
    def format_currency(
        self,
        number: float | decimal.Decimal | str,
        currency: str,
        *,
        format: str | None = None,
        currency_digits: bool = True,
        format_type: t.Literal["name", "standard", "accounting"] = "standard",
        quantization: bool = True,
        group_separator: bool = True,
        numbering_system: str = "latn",
        locale: str | None = None,
    ) -> str:
        return format_currency(
            number=number,
            currency=currency,
            format=format,
            format_type=format_type,
            currency_digits=currency_digits,
            quantization=quantization,
            group_separator=group_separator,
            numbering_system=numbering_system,
            locale=locale if locale else self.get_current_locale(),
        )

    @wraps(format_compact_currency)
    def format_compact_currency(
        self,
        number: float | decimal.Decimal | str,
        currency: str,
        *,
        fraction_digits: int = 0,
        numbering_system: str = "latn",
        locale: str | None = None,
    ) -> str:
        return format_compact_currency(
            number=number,
            currency=currency,
            fraction_digits=fraction_digits,
            numbering_system=numbering_system,
            locale=locale if locale else self.get_current_locale(),
        )

    @wraps(format_percent)
    def format_percent(
        self,
        number: float | decimal.Decimal | str,
        *,
        format: str | None = None,
        quantization: bool = True,
        group_separator: bool = True,
        numbering_system: str = "latn",
        locale: str | None = None,
    ) -> str:
        return format_percent(
            number=number,
            format=format,
            quantization=quantization,
            group_separator=group_separator,
            numbering_system=numbering_system,
            locale=locale if locale else self.get_current_locale(),
        )

    @wraps(format_scientific)
    def format_scientific(
        self,
        number: float | decimal.Decimal | str,
        *,
        format: str | None = None,
        quantization: bool = True,
        numbering_system: str = "latn",
        locale: str | None = None,
    ) -> str:
        return format_scientific(
            number=number,
            format=format,
            quantization=quantization,
            numbering_system=numbering_system,
            locale=locale if locale else self.get_current_locale(),
        )
