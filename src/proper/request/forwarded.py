# Based on code from the aiohttp project, Copyright 2013-2017 by Nikolay Kim and
# Andrew Svetlov, with modifications for the Falcon project by Kurt Griffiths,
# and modifications for the Proper project by Juan-Pablo Scaletti.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import re
import string


# '-' at the end to prevent interpretation as range in a char class
RE_TCHAR = string.digits + string.ascii_letters + r"!#$%&'*+.^_`|~-"

RE_TOKEN = r"[{tchar}]+".format(tchar=RE_TCHAR)

# qdtext includes 0x5C to escape 0x5D ('\]')
# qdtext excludes obs-text (because obsoleted, and encoding not specified)
RE_QDTEXT = r"[{0}]".format(
    r"".join(chr(c) for c in (0x09, 0x20, 0x21) + tuple(range(0x23, 0x7F)))
)

RE_QUOTED_PAIR = r"\\[\t !-~]"

RE_QUOTED_STRING = r'"(?:{quoted_pair}|{qdtext})*"'.format(
    qdtext=RE_QDTEXT, quoted_pair=RE_QUOTED_PAIR
)

RE_FORWARDED_PAIR = r"({token})=({token}|{quoted_string})".format(
    token=RE_TOKEN, quoted_string=RE_QUOTED_STRING
)

RX_FORWARDED_PAIR = re.compile(RE_FORWARDED_PAIR)


def parse_forwarded(val: str | None) -> list[dict]:
    """Parse the value of a `Forwarded` header as specified by RFC 7239.

    - It checks that every value has valid syntax in general as specified
      in section 4: either a 'token' or a 'quoted-string'.
    - It un-escapes found escape sequences.
    - It does NOT validate 'by' and 'for' contents as specified in section
      6.
    - It does NOT validate 'host' contents (Host ABNF).
    - It does NOT validate 'proto' contents for valid URI scheme names.

    Args:
        val (str|None):
            Value of a `Forwarded` header

    Returns:
        List of Forwarded instances, representing each forwarded-element
        in the header, in the same order as they appeared in the header.

    """
    if val is None:
        return []

    elements = []
    pos = 0
    end = len(val)
    need_separator = False
    parsed_element = None

    while 0 <= pos < end:
        match = RX_FORWARDED_PAIR.match(val, pos)

        if match is not None:  # got a valid forwarded-pair
            if need_separator:
                # bad syntax here, skip to next comma
                pos = val.find(",", pos)

            else:
                pos += len(match.group(0))
                need_separator = True

                name, value = match.groups()

                # According to RFC 7239, parameter
                # names are case-insensitive.
                name = name.lower()

                if value[0] == '"':
                    value = value[1:-1]

                # If this is the first pair we've encountered
                # for this forwarded-element, initialize a new object.
                if not parsed_element:
                    parsed_element = dict()

                if name == "by":
                    parsed_element["by"] = value  # destination
                elif name == "for":
                    parsed_element["for"] = value  # source
                elif name == "host":
                    parsed_element["host"] = value
                elif name == "proto":
                    # RFC 7239 only requires that
                    # the "proto" value conform to the Host ABNF
                    # described in RFC 7230. The Host ABNF, in turn,
                    # does not require that the scheme be in any
                    # particular case, so we normalize it here to be
                    # consistent with the WSGI spec that *does*
                    # require the value of 'wsgi.url_scheme' to be
                    # either 'http' or 'https' (case-sensitive).
                    parsed_element["proto"] = value.lower()

        elif val[pos] == ",":  # next forwarded-element
            need_separator = False
            pos += 1

            # It's possible that we arrive here without a
            # parsed element if the header is malformed.
            if parsed_element:
                elements.append(parsed_element)
                parsed_element = None

        elif val[pos] == ";":  # next forwarded-pair
            need_separator = False
            pos += 1

        elif val[pos] in " \t":
            # Allow whitespace even between forwarded-pairs, though
            # RFC 7239 doesn't. This simplifies code and is in line
            # with Postel's law.
            pos += 1

        else:
            # bad syntax here, skip to next comma
            pos = val.find(",", pos)

    # Add the last forwarded-element, if any
    if parsed_element:
        elements.append(parsed_element)

    return elements
