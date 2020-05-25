from .route import Route


__all__ = ("Forward", "forward", )


class Forward(Route):
    """A special kind of route that forward the request to another application with
    its own router.

    Arguments are:

        path (str):
            The path of this route.

        to (str or callable):
            Optional. A reference to the controller that this route is connected to.
            Can be a imported `MyClass.method` or a string `"MyClass.method"`,
            to be imported later from a controllers folder.

        name (str):
            Optional. Overwrites the default name of the route that is the qualified
            name of the `to` method. eg: `PagesController.show`.
            This name can be any unique string eg: "login", "index",
            "something.foobar", etc.

        host (str):
            Optional. Host for this route, including any subdomain
            and an optional port. Examples: "www.example.com", "localhost:5000".

        rules (list or tuple):
            Optional. If `path` contains placeholders, this dict can be used to
            specify the constraints a value must have to match. Without a rule, a
            placeholder will match to everything except slashes.

            ```python
            rules={"<placeholder>": "<constraint>", ...}
            ```

            You can use as constraints regular expressions or one of:
            "int", "float" or "path", that"ll be converted to regular
            expressions for integers, floats or everything *including* slashes.
            Example:

            ```python
            rules={
                "item_id": "int",
                "locales": "(en|es|pt)",
                "path": "path",
                ...
            }
            ```

            Note that this doesn't make type conversions, all values will be passed to
            the controller as strings.

    """

    def __init__(self, path, to, *, name=None, host=None, rules=None):
        assert callable(to), "You can forward only to an WSGI application."
        super().__init__(
            "forward", path, to=to, name=name, host=host, rules=rules,
        )
        self.forward_to = to


forward = Forward
