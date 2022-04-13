import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import List


__all__ = ("parse_comma_separated",)

RX_COMMA = re.compile(r",\s*")


def parse_comma_separated(header="") -> "List[str]":
    """Parse a comma-separated list of values into a
    list of strings.
    """
    return RX_COMMA.split(header)
