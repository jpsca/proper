import decimal
import typing as t
from decimal import (
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_FLOOR,
    ROUND_HALF_DOWN,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    ROUND_UP,
    Decimal,
    InvalidOperation,
)

import babel.numbers as babel_numbers

from .http import format_locale


_HUMAN_SIZE_UNITS = ("Bytes", "KB", "MB", "GB", "TB", "PB", "EB")
_HUMAN_SIZE_BASE = 1024
_ROUND_MODES = {
    "up": ROUND_UP,
    "down": ROUND_DOWN,
    "half_up": ROUND_HALF_UP,
    "half_down": ROUND_HALF_DOWN,
    "half_even": ROUND_HALF_EVEN,
    "ceiling": ROUND_CEILING,
    "floor": ROUND_FLOOR,
    "default": ROUND_HALF_UP,
}


def format_size(
    number: str | int | float | Decimal | None,
    *,
    precision: int = 3,
    significant: bool = True,
    strip_zeros: bool = True,
    round_mode: str = "default",
    locale: str = "en",
) -> str:
    """Format a byte count as a human-readable string with binary (1024) units.

    ```python
    format_size(120)
    # => '120 Bytes'

    format_size(1024)
    # => '1 KB'

    format_size(15_678)
    # => '15.3 KB'

    format_size(133_235_678)
    # => '127 MB'

    format_size(133_235_678, precision=5)
    # => '127.06 MB'

    format_size(133_235_678, precision=5, locale="de")
    # => '127,06 MB'
    ```

    Arguments:
        number:
            the byte count to format.
        precision:
            the number of significant digits to include.
        significant:
            If True, `precision` is the number of significant digits.
            If False, it's the number of fractional digits (defaults to True).
        strip_zeros:
            whether to remove trailing zeros after the decimal point.
        round_mode:
            how to round the number; must be one of ["up", "down", "half_up",
            "half_down", "half_even", "ceiling, "floor, "default"].
        locale:
            force the locale to use for formatting.

    """
    if number is None:
        return ""
    try:
        n = Decimal(str(number))
    except (InvalidOperation, ValueError):
        return ""
    if not n.is_finite():
        return "inf" if n > 0 else "-inf"

    rounding = _ROUND_MODES[round_mode]
    abs_n = abs(n)

    exp = 0
    threshold = Decimal(_HUMAN_SIZE_BASE)
    while abs_n >= threshold and exp < len(_HUMAN_SIZE_UNITS) - 1:
        exp += 1
        threshold *= _HUMAN_SIZE_BASE

    unit = _HUMAN_SIZE_UNITS[exp]

    if exp == 0:
        return f"{format_decimal(int(n), locale=locale)} {unit}"

    scaled = n / Decimal(_HUMAN_SIZE_BASE**exp)
    rounded = _round_decimal(scaled, precision, significant, rounding)
    formatted = _format_with_babel(rounded, locale, strip_zeros)
    return f"{formatted} {unit}"


def _round_decimal(
    value: Decimal, precision: int, significant: bool, rounding: str
) -> Decimal:
    # Construct the quantize target as 1×10^exp via the tuple form.
    # Decimal(10) ** exp is unsafe here: for positive exp it yields
    # Decimal('10'), Decimal('100'), … with exponent 0, which would round
    # to the nearest integer instead of the nearest 10, 100, …
    if significant:
        if value == 0:
            return Decimal(0)
        # adjusted() = exponent of the most-significant digit.
        # 1.18 → 0, 470 → 2, 0.012 → -2.
        exp = value.adjusted() - precision + 1
    else:
        exp = -precision
    return value.quantize(Decimal((0, (1,), exp)), rounding=rounding)


def _format_with_babel(value: Decimal, locale, strip_zeros: bool) -> str:
    # decimal_quantization=False: we've already rounded, don't let Babel
    # re-round to the format pattern's fraction width.
    if strip_zeros:
        # Default pattern (#,##0.###) keeps trailing zeros optional, so
        # Decimal('1.20') comes out as "1.2".
        return babel_numbers.format_decimal(value, locale=locale, decimal_quantization=False)

    # Pad to the value's own scale so trailing zeros survive: a Decimal of
    # exponent -2 (like '1.20' or '500.00') gets pattern "#,##0.00".
    exponent = value.as_tuple().exponent
    scale = -exponent if isinstance(exponent, int) else 0
    if scale > 0:
        pattern = "#,##0." + ("0" * scale)
    else:
        pattern = "#,##0"
    return babel_numbers.format_decimal(value, format=pattern, locale=locale, decimal_quantization=False)


# ----


def format_decimal(
    number: float | decimal.Decimal | str,
    *,
    quantization: bool = True,
    group_separator: bool = True,
    numbering_system: str = "latn",
    locale: str = "en",
) -> str:
    """Formats a number for a specific locale.

    ```python
    format_decimal(12345.5, locale='en_US')
    # => '12,345.5'

    format_decimal(1.2345, locale='de')
    # => '1,234'
    ```

    You can also switch the group separator off:

    ```python
    format_decimal(12345.67, locale='fr_CA', group_separator=False)
    # => '12345,67'
    ```

    By default the locale is allowed to truncate and round a high-precision
    number by forcing its format pattern onto the decimal part. You can bypass
    this behavior with the `quantization` parameter:

    ```python
    format_decimal(1.2346, locale='en_US')
    # => '1.235'

    format_decimal(1.2346, locale='en_US', quantization=False)
    # => '1.2346'
    ```

    Arguments:
        number:
            the number to format.
        quantization:
            truncate and round high-precision numbers to the format pattern. Defaults to `True`.
        group_separator:
            boolean to switch group separator on/off in a locale's number format.
        numbering_system:
            the numbering system used for formatting number symbols. Defaults to "latn".
            the special value "default" will use the default numbering system of the locale.
        locale:
            force the locale to use for formatting.

    Raises:
        `UnsupportedNumberingSystemError`: If the numbering system is not supported by the locale.

    """
    return babel_numbers.format_decimal(
        number,
        decimal_quantization=quantization,
        group_separator=group_separator,
        numbering_system=numbering_system,
        locale=format_locale(locale) if locale else None,
    )


def format_compact_decimal(
    number: float | decimal.Decimal | str,
    *,
    format_type: t.Literal["short", "long"] = "short",
    fraction_digits: int = 0,
    numbering_system: str = "latn",
    locale: str = "en",
) -> str:
    """Like `format_decimal` but in compact form.

    ```python
    format_compact_decimal(12_345, format_type="short", locale='en_US')
    # => '12K'

    format_compact_decimal(12_345, format_type="long", locale='en_US')
    # => '12 thousand'

    format_compact_decimal(12_345, format_type="short", locale='en_US', fraction_digits=2)
    # => '12.34K'

    format_compact_decimal(1_234_567, format_type="short", locale="ja_JP")
    # => '123万'

    format_compact_decimal(2_345_678, format_type="long", locale="mk")
    # => '2 милиони'

    format_compact_decimal(21_000_000, format_type="long", locale="mk")
    # => '21 милион'

    format_compact_decimal(12_345, format_type="short", locale='ar_EG', fraction_digits=2, numbering_system='default')
    # => '12٫34\xa0ألف'
    ```

    Arguments:
        number:
            the number to format.
        format_type:
            compact format to use ("short" or "long").
        fraction_digits:
            number of digits after the decimal point to use. Defaults to `0`.
        numbering_system:
            the numbering system used for formatting number symbols. Defaults to "latn".
            the special value "default" will use the default numbering system of the locale.
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
        locale=format_locale(locale) if locale else None,
    )


def format_currency(
    number: float | decimal.Decimal | str,
    currency: str,
    *,
    format: str | None = None,
    currency_digits: bool = True,
    format_type: t.Literal["name", "standard", "accounting"] = "standard",
    quantization: bool = True,
    group_separator: bool = True,
    numbering_system: str = "latn",
    locale: str = "en",
) -> str:
    """Formats a number (as a float, Decimal, or string) as a currency value,
    following the locale's formatting rules.

    ```python
    format_currency(1_099.98, 'USD', locale='en_US')
    # => '$1,099.98'

    format_currency(1_099.98, 'USD', locale='es_CO')
    # => 'US$1.099,98'

    format_currency(1_099.98, 'EUR', locale='de_DE')
    # => '1.099,98\xa0\u20ac'

    format_currency(1_099.98, 'EGP', locale='ar_EG', numbering_system='default')
    # => '\u200f1٬099٫98\xa0ج.م.\u200f'
    ```

    The format can also be specified explicitly.  The currency is
    placed with the '¤' sign.  As the sign gets repeated the format
    expands (¤ being the symbol, ¤¤ is the currency abbreviation and
    ¤¤¤ is the full name of the currency):

    ```python
    format_currency(1_099.98, 'EUR', format='¤¤ #,##0.00', locale='en_US')
    # => 'EUR 1,099.98'
    format_currency(1_099.98, 'EUR', format='#,##0.00 ¤¤¤', locale='en_US')
    # => '1,099.98 euros'
    ```

    Currencies usually have a specific number of decimal digits. This function
    favours that information over the given format:

    ```python
    format_currency(1_099.98, 'JPY', locale='en_US')
    # => '\xa51,100'

    format_currency(1_099.98, 'COP', format='#,##0.00', locale='es_ES')
    # => '1.099,98'
    ```

    However, the number of decimal digits can be overridden from the currency
    information, by setting the last parameter to `False`:

    ```python
    format_currency(1_099.98, 'JPY', locale='en_US', currency_digits=False)
    # => '\xa51,099.98'

    format_currency(1_099.98, 'COP', format='#,##0.00', locale='es_ES', currency_digits=False)
    # => '1.099,98'
    ```

    If a format is not specified the type of currency format to use
    from the locale can be specified:

    ```python
    format_currency(1_099.98, 'EUR', locale='en_US', format_type='standard')
    # => '\u20ac1,099.98'
    ```

    When the given currency format type is not available, an exception is
    raised:

    ```python
    format_currency('1_099.98', 'EUR', locale='root', format_type='unknown')
    Traceback (most recent call last):
        ...
    UnknownCurrencyFormatError: "'unknown' is not a known currency format type"
    ```

    You can also switch the group separator off:

    ```python
    format_currency(101_299.98, 'USD', locale='en_US', group_separator=False)
    # => '$101299.98'

    ```

    You can also pass format_type='name' to use long display names. The order of
    the number and currency name, along with the correct localized plural form
    of the currency name, is chosen according to locale:

    ```python
    format_currency(1, 'USD', locale='en_US', format_type='name')
    # => '1.00 US dollar'

    format_currency(1_099.98, 'USD', locale='en_US', format_type='name')
    # => '1,099.98 US dollars'

    format_currency(1_099.98, 'USD', locale='ee', format_type='name')
    # => 'us ga dollar 1,099.98'
    ```

    By default the locale is allowed to truncate and round a high-precision
    number by forcing its format pattern onto the decimal part. You can bypass
    this behavior with the `quantization` parameter:

    ```python
    format_currency(1_099.9876, 'USD', locale='en_US')
    # => '$1,099.99'

    format_currency(1_099.9876, 'USD', locale='en_US', quantization=False)
    # => '$1,099.9876'
    ```

    Arguments:
        number:
            The number to format.
        currency:
            The currency code.
        format:
            The format string to use.
        format_type:
            The currency format type to use. Can be "name", "standard" or "accounting".
            Defaults to "standard".
        currency_digits:
            Use the currency's natural number of decimal digits or not. Defaults to `True`.
        quantization:
            Truncate and round high-precision numbers to the format pattern. Defaults to `True`.
        group_separator:
            Boolean to switch group separator on/off in a locale's number format.
        numbering_system:
            The numbering system used for formatting number symbols. Defaults to "latn".
            The special value "default" will use the default numbering system of the locale.
        locale:
            Force the locale to use for formatting.

    Raises:
        `UnsupportedNumberingSystemError`: If the numbering system is not supported by the locale.
    """
    return babel_numbers.format_currency(
        number=number,
        currency=currency,
        format=format,
        format_type=format_type,
        currency_digits=currency_digits,
        decimal_quantization=quantization,
        group_separator=group_separator,
        numbering_system=numbering_system,
        locale=format_locale(locale) if locale else None,
    )


def format_compact_currency(
    number: float | decimal.Decimal | str,
    currency: str,
    *,
    fraction_digits: int = 0,
    numbering_system: str = "latn",
    locale: str = "en",
) -> str:
    """Like `format_currency` but in compact form.

    ```python
    format_compact_currency(12_345, 'USD', locale='en_US')
    # => '$12K'
    format_compact_currency(123_456_789, 'USD', locale='en_US', fraction_digits=2)
    # => '$123.46M'
    format_compact_currency(123_456_789, 'EUR', locale='de_DE', fraction_digits=1)
    # => '123,5\xa0Mio.\xa0€'
    ```

    Arguments:
        number:
            the number to format.
        currency:
            the currency code.
        fraction_digits:
            number of digits after the decimal point to use. Defaults to `0`.
        numbering_system:
            the numbering system used for formatting number symbols. Defaults to "latn".
            the special value "default" will use the default numbering system of the locale.
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
        locale=format_locale(locale) if locale else None,
    )


def format_percent(
    number: float | decimal.Decimal | str,
    *,
    format: str | None = None,
    quantization: bool = True,
    group_separator: bool = True,
    numbering_system: str = "latn",
    locale: str = "en",
) -> str:
    """Return formatted percent value following the locale's formatting rules.

    ```python
    format_percent(0.34, locale='en_US')
    # => '34%'

    format_percent(25.1234, locale='en_US')
    # => '2,512%'

    format_percent(25.1234, locale='sv_SE')
    # => '2\xa0512\xa0%'

    format_percent(25.1234, locale='ar_EG', numbering_system='default')
    # => '2٬512%'
    ```

    The format pattern can also be specified explicitly:

    ```python
    format_percent(25.1234, format='#,##0\u2030', locale='en_US')
    # => '25,123‰'
    ```

    And you can switch the group separator off:

    ```python
    format_percent(229_291.1234, locale='pt_BR', group_separator=False)
    # => '22929112%'
    ```

    By default the locale is allowed to truncate and round a high-precision
    number by forcing its format pattern onto the decimal part. You can bypass
    this behavior with the `quantization` parameter:

    ```python
    format_percent(23.9876, locale='en_US')
    # => '2,399%'

    format_percent(23.9876, locale='en_US', quantization=False)
    # => '2,398.76%'
    ```

    Arguments:
        number:
            The number to format as a percent.
        format:
            The format string to use.
        quantization:
            Truncate and round high-precision numbers to the format pattern. Defaults to `True`.
        group_separator:
            Boolean to switch group separator on/off in a locale's number format.
        numbering_system:
            The numbering system used for formatting number symbols. Defaults to "latn".
            The special value "default" will use the default numbering system of the locale.
        locale:
            Force the locale to use for formatting.

    Raises:
        `UnsupportedNumberingSystemError`: If the numbering system is not supported by the locale.

    """
    return babel_numbers.format_percent(
        number=number,
        format=format,
        decimal_quantization=quantization,
        group_separator=group_separator,
        numbering_system=numbering_system,
        locale=format_locale(locale) if locale else None,
    )


def format_scientific(
    number: float | decimal.Decimal | str,
    *,
    format: str | None = None,
    quantization: bool = True,
    numbering_system: str = "latn",
    locale: str = "en",
) -> str:
    """Formats a number in scientific notation following the locale's formatting rules.

    ```python
    format_scientific(10_000, locale='en_US')
    # => '1E4'

    format_scientific(10_000, locale='ar_EG', numbering_system='default')
    # => '1أس4'
    ```

    The format pattern can also be specified explicitly:

    ```python
    format_scientific(1_234_567, format='##0.##E00', locale='en_US')
    # => '1.23E06'
    ```

    By default the locale is allowed to truncate and round a high-precision
    number by forcing its format pattern onto the decimal part. You can bypass
    this behavior with the `quantization` parameter:

    ```python
    format_scientific(1_234.9876, format='#.##E0', locale='en_US')
    # => '1.23E3'

    format_scientific(1_234.9876, format='#.##E0', locale='en_US', quantization=False)
    # => '1.2349876E3'
    ```

    Arguments:
        number:
            The number to format in scientific notation.
        format:
            The format string to use.
        quantization:
            Truncate and round high-precision numbers to the format pattern. Defaults to `True`.
        numbering_system:
            The numbering system used for formatting number symbols. Defaults to "latn".
            The special value "default" will use the default numbering system of the locale.
        locale:
            Force the locale to use for formatting.

    Raises:
        `UnsupportedNumberingSystemError`: If the numbering system is not supported by the locale.

    """
    return babel_numbers.format_scientific(
        number=number,
        format=format,
        decimal_quantization=quantization,
        numbering_system=numbering_system,
        locale=format_locale(locale) if locale else None,
    )

