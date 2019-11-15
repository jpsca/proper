"""
## proper.support.inflector

"""
import re


__all__ = ("pascal_to_snake", "snake_to_pascal", "titleize")

NON_ALPHANUMDOT_RE = re.compile("[^A-Z^a-z^0-9^.]+")
FIRST_CAP_RE = re.compile("(.)([A-Z][a-z]+)")
ALL_CAP_RE = re.compile("([a-z0-9])([A-Z])")
SPACES = re.compile(r"\s+")


def pascal_to_snake(name):
    """Converts PascalCase or camelCase to snake_case.

    >>> pascal_to_snake('Pascal')
    'pascal'
    >>> pascal_to_snake('PascalCase')
    'pascal_case'
    >>> pascal_to_snake('PascalPascalCase')
    'pascal_pascal_case'
    >>> pascal_to_snake('Pascal_Pascal_Case')
    'pascal_pascal_case'
    >>> pascal_to_snake('Pascal2Pascal2Case')
    'pascal2_pascal2_case'
    >>> pascal_to_snake('getHTTPResponseCode')
    'get_http_response_code'
    >>> pascal_to_snake('get2HTTPResponseCode')
    'get2_http_response_code'
    >>> pascal_to_snake('HTTPResponseCode')
    'http_response_code'
    >>> pascal_to_snake('HTTPResponseCodeXYZ')
    'http_response_code_xyz'
    >>> pascal_to_snake('PageController.index')
    'page_controller.index'
    >>> pascal_to_snake('already_in_snake_case')
    'already_in_snake_case'

    """
    s1 = FIRST_CAP_RE.sub(r"\1_\2", name)
    s2 = ALL_CAP_RE.sub(r"\1_\2", s1)
    return s2.replace("__", "_").lower()


def snake_to_pascal(name):
    """Converts snake_case to PascalCase.

    Is the opposite of `pascal_to_snake` except for can't restore ALLCAPS words.
    It will remove non alphanumeric character from the word first, so "who's online"
    will be converted to "WhoSOnline".

    >>> snake_to_pascal('pascal')
    'Pascal'
    >>> snake_to_pascal('pascal_case')
    'PascalCase'
    >>> snake_to_pascal('pascal_pascal_case')
    'PascalPascalCase'
    >>> snake_to_pascal('pascal__pascal__case')
    'PascalPascalCase'
    >>> snake_to_pascal('pascal2_pascal2_case')
    'Pascal2Pascal2Case'
    >>> snake_to_pascal('get_http_response_code')
    'GetHttpResponseCode'
    >>> snake_to_pascal('get_HTTP_response_code')
    'GetHTTPResponseCode'

    """
    name = NON_ALPHANUMDOT_RE.sub("_", name)
    return "".join(w[0].upper() + w[1:] for w in name.split("_"))


def titleize(word):
    """
    Capitalize all the words and replace some characters in the string to
    create a nicer looking title..

    Examples:
      >>> titleize('man from the boondocks')
      'Man From The Boondocks'
      >>> titleize('x-men: the Last stand')
      'X-Men: The Last Stand'
      >>> titleize('TheManWithoutAPast')
      'The Man Without A Past'
      >>> titleize('raiders_of_the_lost_ark')
      'Raiders Of The Lost Ark'

    """
    return pascal_to_snake(SPACES.sub("_", word)).replace("_", " ").title()
