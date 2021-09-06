"""A super simple slugify helper.

If if it is too simple for your needs you might want to use
https://github.com/un33k/python-slugify
"""
import re

import inflection


rx_pars = re.compile(r"\([^)]+\)")
rx_extra = re.compile(r"[^-a-zA-Z0-9]+")


def slugify(text, space="-", lower=True, nopars=True, nodots=True, strict=True):
    """Transform an unicode text into its approximate ASCII version so it can
    be used in a URL.

    Arguments are:

        space (str):
            Char to use as words separator

        lower (bool):
             Lowercase the result

        nopars (bool):
            Removes any text inside parentheses

        nodots (bool):
            remove dots to prevent U.S.A -> U-S-A

        strict (bool):
            Replace symbols, except for "-", with space

    Exaples:

    slugify("Héllø Wörld, Olé!")
    'hello-world-ole'

    >>> slugify("Python’s Enum makes me (a little) angry")
    'pythons-enum-makes-me-angry'

    >>> slugify("Python’s Enum makes me (a little) angry", nopars=False)
    'pythons-enum-makes-me-a-little-angry'

    >>> slugify("The man from U.N.C.L.E.")
    'the-man-from-uncle'

    >>> slugify("The man from U.N.C.L.E.", nodots=False)
    'the-man-from-u-n-c-l-e'

    slugify("my four-years-old son")
    'my-four-years-old-son'

    """
    atext = inflection.transliterate(text)
    if lower:
        atext = atext.lower()

    if nopars:
        atext = rx_pars.sub(space, atext)

    if nodots:
        atext = atext.replace(".", "")

    if strict:
        atext = rx_extra.sub(space, atext)

    # Remove duplicated spaces
    atext = re.sub(space + "{2,}", space, atext).strip(space)
    return atext
