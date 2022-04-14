import re
from operator import itemgetter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import List, Tuple


RX_ACCEPT = re.compile(
    r"""
    (                       # media-range capturing-parenthesis
      [^\s;,]+              # type/subtype
      (?:[ \t]*;[ \t]*      # ";"
        (?:                 # parameter non-capturing-parenthesis
          [^\s;,q][^\s;,]*  # token that doesn't start with "q"
        |                   # or
          q[^\s;,=][^\s;,]* # token that is more than just "q"
        )
      )*                    # zero or more parameters
    )                       # end of media-range
    (?:[ \t]*;[ \t]*q=      # weight is a "q" parameter
      (\d*(?:\.\d+)?)       # qvalue capturing-parentheses
      [^,]*                 # "extension" accept params: who cares?
    )?                      # accept params are optional
    """,
    re.VERBOSE,
)


def parse_accept_header(value: str) -> "List[Tuple[str, float]]":
    """Parses an HTTP Accept-* header. Does not implement a complete
    valid algorithm but one that support most cases.
    Returns a list of `(value, quality)` tuples sorted by the quality.

    https://datatracker.ietf.org/doc/html/rfc7231#section-5.3.2
    """
    result: "List[Tuple[str, float]]" = []
    if not value:
        return result

    for match in RX_ACCEPT.finditer(value):
        quality_match = match.group(2)
        if not quality_match:
            quality: float = 1
        else:
            quality = max(min(float(quality_match), 1), 0)
        result.append((match.group(1), quality))

    return sorted(result, key=itemgetter(1))
