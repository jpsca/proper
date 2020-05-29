"""
Utilities to declare routes in your application.

"""
from .base import BaseRoute


__all__ = (
    "Route",
    "Get",
    "Post",
    "Put",
    "Delete",
    "Options",
    "Patch",
    "route",
    "get",
    "post",
    "put",
    "delete",
    "options",
    "patch",
)


class Route(BaseRoute):
    """
    Arguments are:

        method (str):
            Usualy, one of the HTTP methods: "get", "head", "post", "put", "delete",
            "connect", "options", "trace" or "patch"; but it could also be another
            application-specific value.

        path (str):
            The path of this route.

        to (str or callable):
            Optional. A reference to the controller that this route is connected to.
            Can be a imported `MyClass.method` or a string `"MyClass.method"`,
            to be imported later.

        name (str):
            Optional. Overwrites the default name of the route that is the qualified
            name of the `to` method. eg: `PagesController.show`.
            This name can be any unique string eg: "login", "index",
            "something.foobar", etc.

        host (str):
            Optional. Host for this route, including any subdomain
            and an optional port. Examples: "www.example.com", "localhost:5000".

        redirect (str):
            Optional. Instead of dispatching to a controller, redirect to this
            other URL.

        redirect_status_code (str):
            Optional. Which status code to use for the redirect.
            The status "307 Temporary Redirect" is the default.

        defaults (dict):
            Optional. A dict with values that will be sent to the controller along to
            those of the placeholders.

        rules (list or tuple):
            Optional. If `path` contains placeholders, this dict can be used to
            specify the constraints a value must have to match. Without a rule, a
            placeholder will match to everything except slashes.

            ```python
            rules={"<placeholder>": "<constraint>", ...}
            ```

            You can use as constraints regular expressions or one of:
            "int", "float" or "path", that'll be converted to regular
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

    __slots__ = (
        "method",
        "path",
        "to",
        "name",
        "host",
        "redirect",
        "redirect_status_code",
        "defaults",
        "rules",
        "forward_to",
        "_re_path",
    )

    def __init__(
        self,
        method,
        path,
        *,
        to=None,
        name=None,
        host=None,
        redirect=None,
        redirect_status_code="307 Temporary Redirect",
        defaults=None,
        rules=None,
    ):
        # Look ma, a practical use case for a XOR!
        assert (to is not None) ^ (
            redirect is not None
        ), "A rule must be created with either a `to` or a `redirect`."

        self.method = method.upper()
        self.path = "/" + path.strip("/")
        self.to = to
        self.name = name or (to.__qualname__ if callable(to) else to)
        self.host = host
        self.redirect = redirect
        self.redirect_status_code = redirect_status_code
        self.defaults = defaults or {}
        self.rules = rules or {}

        self.forward_to = None

        super().__init__()

    def __repr__(self):
        return (
            f"<route {self.method} {self.path}"
            + (f" “{self.name}”" if self.name else "")
            + (f" host={ self.host}" if self.host else "")
            + (f" redirect={self.redirect} " if self.redirect else "")
            + ">"
        )

    @property
    def build_only(self):
        return not (self.to or self.redirect or self.forward_to)


class Get(Route):
    def __init__(self, path, **kwargs):
        super().__init__("GET", path, **kwargs)


class Post(Route):
    def __init__(self, path, **kwargs):
        super().__init__("POST", path, **kwargs)


class Put(Route):
    def __init__(self, path, **kwargs):
        super().__init__("PUT", path, **kwargs)


class Delete(Route):
    def __init__(self, path, **kwargs):
        super().__init__("DELETE", path, **kwargs)


class Options(Route):
    def __init__(self, path, **kwargs):
        super().__init__("OPTIONS", path, **kwargs)


class Patch(Route):
    def __init__(self, path, **kwargs):
        super().__init__("PATCH", path, **kwargs)


route = Route
get = Get
post = Post
put = Put
delete = Delete
options = Options
patch = Patch
