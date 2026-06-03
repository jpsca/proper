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

from babel.numbers import format_decimal


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
        return format_decimal(value, locale=locale, decimal_quantization=False)

    # Pad to the value's own scale so trailing zeros survive: a Decimal of
    # exponent -2 (like '1.20' or '500.00') gets pattern "#,##0.00".
    exponent = value.as_tuple().exponent
    scale = -exponent if isinstance(exponent, int) else 0
    if scale > 0:
        pattern = "#,##0." + ("0" * scale)
    else:
        pattern = "#,##0"
    return format_decimal(value, format=pattern, locale=locale, decimal_quantization=False)
