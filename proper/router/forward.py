from .route import Route


__all__ = ("Forward", "forward", )


class Forward(Route):
    """A special kind of route that forward the request to another application with
    its own router.

    Arguments are:

        path (str):
            The path of this route.
            Can contain placeholders like `:name` or `:name<format>` where format can be:

            - nothing, for matching anything except slashes
            - `int` or `float`, for matching numbers
            - `path`, for matching anything *including* slashes
            - a regular expression

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

    """

    def __init__(self, path, to, *, name=None, host=None):
        assert callable(to), "You can forward only to an WSGI application."
        super().__init__("forward", path, to=to, name=name, host=host)
        self.forward_to = to


forward = Forward
