
import typing as t
from datetime import datetime

from ..types import Iterable


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

    version = str(0 if version is None else version)

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

    version = str(0 if version is None else version)

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
        key_context = t.cast(TCollection, key_context)
        return key_for_collection(prefix, key_context, version=version)

    return key_for_object(prefix, key_context, version=version)

