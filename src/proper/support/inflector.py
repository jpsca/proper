import re


__all__ = ("pascal_to_snake", "titleize")

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
