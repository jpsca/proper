import typing as t

from jinja2 import Environment, nodes
from jinja2.ext import Extension

from .keys import key_for


class FragmentCacheExtension(Extension):
    # a set of names that trigger the extension.
    tags = {"cache"}

    def __init__(self, environment: Environment):
        super().__init__(environment)

    def parse(self, parser):
        # the first token is the token that started the tag.  In our case
        # we only listen to ``'cache'`` so this will be a name token with
        # `cache` as value.  We get the line number so that we can give
        # that line number to the nodes we create by hand.
        lineno = next(parser.stream).lineno

        # now we parse a single expression that is used as cache key
        # or an object or a collection of objects from where to derive
        # the key
        args, kwargs, dyn_args, dyn_kwargs = parser.parse_call_args()
        args = [] if args is None else args
        kwargs = [] if kwargs is None else kwargs

        nameKw = nodes.Keyword()
        nameKw.key = "name"
        nameKw.value = nodes.Const(parser.name or "")
        kwargs.append(nameKw)

        # now we parse the body of the cache block up to `endcache` and
        # drop the needle (which would always be `endcache` in that case)
        body = parser.parse_statements(("name:endcache",), drop_needle=True)

        # now return a `CallBlock` node that calls our _cache_support
        # helper method on this extension.
        return nodes.CallBlock(
            self.call_method("_cache_support", args, kwargs), [], [], body
        ).set_lineno(lineno)

    def _cache_support(
        self,
        key_context: str,
        *,
        caller: t.Callable,
        name: str,
        expires_in: int | None = None,
        version: str | int | None = None,
    ):
        prefix = name or "view"
        key = key_for(prefix=prefix, key_context=key_context, version=version)
        app_cache = self.environment.app_cache  # type: ignore

        value = app_cache.get(key, expires_in=expires_in)
        if value is not None:
            return value

        value = caller()
        app_cache.set(key, value)
        return value

