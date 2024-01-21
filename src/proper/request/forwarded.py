# Based on code from the aiohttp project, Copyright aio-libs contributors,
# with modifications for the Proper project.
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

RE_TOKEN = rf"[{RE_TCHAR}]+"

# qdtext includes 0x5C to escape 0x5D ('\]')
# qdtext excludes obs-text (because obsoleted, and encoding not specified)
RE_QDTEXT = r"[{}]".format(
    r"".join(chr(c) for c in (0x09, 0x20, 0x21) + tuple(range(0x23, 0x7F)))
)

RE_QUOTED_PAIR = r"\\[\t !-~]"

RE_QUOTED_STRING = r'"(?:{quoted_pair}|{qdtext})*"'.format(
    qdtext=RE_QDTEXT, quoted_pair=RE_QUOTED_PAIR
)

RE_FORWARDED_PAIR = r"({token})=({token}|{quoted_string})(:\d{{1,4}})?".format(
    token=RE_TOKEN, quoted_string=RE_QUOTED_STRING
)

# same pattern as _QUOTED_PAIR but contains a capture group
RX_QUOTED_PAIR_REPLACE = re.compile(r"\\([\t !-~])")

RX_FORWARDED_PAIR = re.compile(RE_FORWARDED_PAIR)


def parse_forwarded(val: str | None) -> list[dict[str, str]]:
    """Parse a `Forwarded` header.

    Makes an effort to parse the header as specified by RFC 7239:

    - It adds one (immutable) dictionary per Forwarded 'field-value', ie
      per proxy. The element corresponds to the data in the Forwarded
      field-value added by the first proxy encountered by the client. Each
      subsequent item corresponds to those added by later proxies.
    - It checks that every value has valid syntax in general as specified
      in section 4: either a 'token' or a 'quoted-string'.
    - It un-escapes found escape sequences.
    - It does NOT validate 'by' and 'for' contents as specified in section 6.
    - It does NOT validate 'host' contents (Host ABNF).
    - It does NOT validate 'proto' contents for valid URI scheme names.

    Arguments:

    - val:
        The raw header value.

    Returns:

    A list of zero or more dictionaries, each containing the parsed
    Forwarded parameters for a proxy.

    """
    if val is None:
        return []

    length = len(val)
    pos = 0
    need_separator = False
    proxies = []
    proxy: dict[str, str] = {}
    proxies.append(proxy)

    while 0 <= pos < length:
        match = RX_FORWARDED_PAIR.match(val, pos)

        if match is not None:  # got a valid forwarded-pair
            if need_separator:
                # bad syntax here, skip to next comma
                pos = val.find(",", pos)
            else:
                name, value, port = match.groups()
                if value[0] == '"':
                    # quoted string: remove quotes and unescape
                    value = RX_QUOTED_PAIR_REPLACE.sub(r"\1", value[1:-1])
                if port:
                    value += port
                proxy[name.lower()] = value
                pos += len(match.group(0))
                need_separator = True

        elif val[pos] == ",":  # next forwarded-proxy
            need_separator = False
            proxy = {}
            proxies.append(proxy)
            pos += 1

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

    return proxies
