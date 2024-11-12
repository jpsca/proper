import typing as t
from collections.abc import Iterable
from datetime import datetime

from jinja2 import Environment, nodes
from jinja2.ext import Extension


if t.TYPE_CHECKING:
    from proper.cache import BaseCache


class HasUpdatedAt(t.Protocol):
    updated_at: datetime | None


TObject = HasUpdatedAt
TCollection = Iterable[TObject]


def key_for_object(
    prefix: str,
    obj: TObject,
    *,
    version: str | int | None = None,
) -> str:
    obj_class = obj.__class__.__name__
    obj_id = getattr(obj, "id", "?")

    if version is None:
        updated_at = getattr(obj, "updated_at", None)
        if updated_at is not None:
            version = str(datetime.timestamp(updated_at))

    version = str(0 if version is None else 0)

    return f"{prefix}:{version}/{obj_class}/{obj_id}".lower()


def key_for_collection(
    prefix: str,
    collection: TCollection,
    *,
    version: str | int | None = None,
) -> str:
    collection = tuple(collection)
    col_class = collection[0].__class__.__name__
    col_size = len(collection)

    if version is None:
        if hasattr(collection[0], "updated_at"):
            max_updated_at = max(
                (obj.updated_at for obj in collection if obj.updated_at is not None),
                default=None,
            )
            if max_updated_at:
                version = str(datetime.timestamp(max_updated_at))

    version = str(0 if version is None else 0)

    return f"{prefix}:{version}/{col_class}/col/{col_size}".lower()


def key_for(
    prefix: str,
    key_context: str | TCollection | TObject,
    *,
    version: str | int | None = None,
) -> t.Any:
    if isinstance(key_context, str):
        return key_context.lower()

    if isinstance(key_context, Iterable):
        if isinstance(key_context, (dict, bytes, bytearray)):
            raise ValueError("key must be either  a string, an object or a collection")
        return key_for_collection(prefix, key_context, version=version)

    return key_for_object(prefix, key_context, version=version)


class FragmentCacheExtension(Extension):
    # a set of names that trigger the extension.
    tags = {"cache"}

    def __init__(self, environment: Environment, cache: "BaseCache"):
        super().__init__(environment)
        environment.extend(frag_cache=cache)

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
        cache = self.environment.frag_cache  # type: ignore

        value = cache.get(key, expires_in=expires_in)
        if value is not None:
            return value

        value = caller()
        cache.set(key, value)
        return value

