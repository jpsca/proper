"""
What file?
This doesn't look like anything to me.

"""
from .base import BaseRoute


# __all__ = ("Channel", "channel", )
__all__ = tuple()


class Channel(BaseRoute):
    """
    Arguments are:

        path (str):
            Channel ID with optional placeholders.

        to (str or callable):
            Optional. A reference to the channel controller class that this channel is
            connected to. Can be a imported `MyClass` or a string `'MyClass'`,
            to be imported later from a *channels* folder.

        name (str):
            Optional. Overwrites the default name of the route that is the qualified
            name of the `to` method. eg: `PagesController.show`.
            This name can be any unique string eg: `'login'`, `'index'`,
            `'something.foobar'`, etc.

        host (str):
            Optional. Host for this channel, including any subdomain
            and an optional port. Examples: `www.example.com`, `localhost:5000`.

        rules (list or tuple):
            Optional. If `name` contains placeholders, this dict can be used to
            specify the constraints a value must have to match. Without a rule, a
            placeholder will match to everything except slashes.

            .. code-block:: python

                rules={'<placeholder>': '<constraint>', ...}

            You can use as constraints regular expressions or one of:
            `'int'`, `'float'` or `'path'`, that'll be converted to regular
            expressions for integers, floats or everything *including* slashes.
            Example:

            .. code-block:: python

                rules={
                    'item_id': 'int',
                    'locales': '(en|es|pt)',
                    'path': 'path',
                    ...
                }

            Note that this doesn't make type conversions, all values will be passed to
            the channel controller as strings.

    """

    __slots__ = ("path", "name", "to", "host", "_re_path")

    def __init__(self, path, to, *, name=None, host=None):
        self.path = path
        self.to = to
        self.name = name
        self.host = host
        super().__init__()


channel = Channel
