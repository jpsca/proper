import re


__all__ = (
    "pascal_to_snake",
    "titleize",
)

RE_NON_ALPHANUMDOT = re.compile("[^A-Z^a-z^0-9^.]+")
RE_FIRST_CAP = re.compile("(.)([A-Z][a-z]+)")
RE_ALL_CAP = re.compile("([a-z0-9])([A-Z])")
RE_SPACES = re.compile(r"\s+")


def pascal_to_snake(text):
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
    s1 = RE_FIRST_CAP.sub(r"\1_\2", text)
    s2 = RE_ALL_CAP.sub(r"\1_\2", s1)
    return s2.replace("__", "_").lower()


def snake_to_pascal(text):
    """Converts snake_case to PascalCase.

    >>> snake_to_pascal('snake')
    'Snake'
    >>> snake_to_pascal('snake_case')
    'SnakeCase'
    >>> snake_to_pascal('snake___case_')
    'SnakeCase'
    >>> snake_to_pascal('Snake_Snake_Case')
    'SnakeSnakeCase'
    >>> snake_to_pascal('getHTTPCode')
    'GetHTTPCode'

    """
    text = text.replace("_", " ").strip()
    return "".join([f"{word[0].upper()}{word[1:]}" for word in RE_SPACES.split(text)])


def titleize(text):
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
    return pascal_to_snake(RE_SPACES.sub("_", text)).replace("_", " ").title()
