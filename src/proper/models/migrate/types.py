"""Peewee-Migrate custom types."""
from typing import Any, TypeVar

from peewee import Model


TModelType = type[Model]
TParams = dict[str, Any]

TVModelType = TypeVar("TVModelType", bound=TModelType)
