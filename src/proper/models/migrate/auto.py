"""Automatically create migrations."""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Final, cast

import peewee as pw
from playhouse import postgres_ext
from playhouse.reflection import Column as VanilaColumn


if TYPE_CHECKING:
    from .migrator import Migrator
    from .types import TModelType, TParams

INDENT: Final = "    "
NEWLINE: Final = "\n" + INDENT
# The name a migration uses for the module of a field class, if not `pw`
FIELD_MODULES: Final = {"playhouse.postgres_ext": "pw_pext"}
PW_MODULES: Final = "playhouse.postgres_ext", "playhouse.fields", "peewee"


def field_module(field_class: type[pw.Field]) -> str:
    """The name a migration uses for the module of a field class.

    It is the module of the class and not its name that tells: Peewee
    and `playhouse.postgres_ext` both have a `JSONField`.
    """
    return FIELD_MODULES.get(field_class.__module__, "pw")


def model_fields_gen(model: "TModelType", *names: str):
    """Get model fields by names.

    Args:
        model (pw.Model): Peewee model.
        *names (str): Field names.

    Returns:
        list: List of fields.
    """
    meta = model._meta
    for field in meta.sorted_fields:
        if field.name in names:
            yield field


def fk_to_params(field: pw.ForeignKeyField) -> TParams:
    """Get params from the given fk."""
    params = {}
    if field.on_delete is not None:
        params["on_delete"] = f"'{field.on_delete}'"

    if field.on_update is not None:
        params["on_update"] = f"'{field.on_update}'"

    return params


def dtf_to_params(field: pw.DateTimeField) -> TParams:
    """Get params from the given datetime field."""
    params = {}
    if field.formats != pw.DateTimeField().formats:
        params["formats"] = repr(field.formats)

    return params


def arrayf_to_params(f: postgres_ext.ArrayField):
    inner_field = cast("pw.Field", vars(f)["_ArrayField__field"])
    module = field_module(inner_field.__class__)
    return {
        "field_class": f"{module}.{inner_field.__class__.__name__}",
        "field_kwargs": repr(Column(inner_field).get_field_parameters()),
        "dimensions": f.dimensions,
        "convert_values": f.convert_values,
    }


FIELD_TO_PARAMS: dict[type[pw.Field], Callable[[Any], TParams]] = {
    pw.CharField: lambda f: {"max_length": f.max_length},
    pw.DecimalField: lambda f: {
        "auto_round": f.auto_round,
        "decimal_places": f.decimal_places,
        "max_digits": f.max_digits,
        "rounding": repr(f.rounding),
    },
    pw.ForeignKeyField: fk_to_params,
    pw.DateTimeField: dtf_to_params,
    postgres_ext.ArrayField: arrayf_to_params,
}


class Column(VanilaColumn):
    """Get field's migration parameters."""

    field_class: type[pw.Field]

    def __init__(self, field: pw.Field, **kwargs):
        super(Column, self).__init__(
            field.name,
            find_field_type(field),
            field.field_type,
            field.null,
            primary_key=field.primary_key,
            column_name=field.column_name,
            index=field.index,
            unique=field.unique,
            **kwargs,
        )
        self.field = field

        if self.field_class in FIELD_TO_PARAMS:
            if self.extra_parameters is None:  # type: ignore[has-type]
                self.extra_parameters = {}

            self.extra_parameters.update(FIELD_TO_PARAMS[self.field_class](field))

        self.rel_model = None
        self.to_field = None

        if isinstance(field, pw.ForeignKeyField):
            self.to_field = field.rel_field.name
            self.rel_model = (
                "'self'"
                if field.rel_model == field.model
                else "migrator.orm['%s']" % field.rel_model._meta.table_name
            )

    def get_field(self, space: str = " ") -> str:
        """Generate the field definition for this column."""
        field = super(Column, self).get_field()
        module = field_module(self.field_class)
        name, _, field = [s and s.strip() for s in field.partition("=")]
        return "{name}{space}={space}{module}.{field}".format(
            name=name, field=field, space=space, module=module
        )

    def get_field_parameters(self, *, change=False) -> TParams:
        """Generate parameters for self field."""
        params = super(Column, self).get_field_parameters()
        params.pop("backref", None)

        if self.field.default is not None and not callable(self.field.default):
            value = self.field.db_value(self.field.default)
            if isinstance(value, pw.WrappedNode):
                params["default"] = str(value.node)
            else:
                params["default"] = repr(value)

        if change:
            params["null"] = self.nullable
            params["unique"] = bool(params.pop("unique", False))
            params["index"] = bool(params.pop("index", False)) or params["unique"]

            params.pop("default", None)
            params.pop("on_delete", None)
            params.pop("on_update", None)

        return params


def diff_model(model: TModelType, source: TModelType, **opts) -> list[str]:
    """Find difference between given peewee models."""
    if model._meta.table_name != source._meta.table_name:
        raise ValueError("Cannot diff models with different table names")  # noqa: EM101, TRY003

    model_field_names = {f.name for f in model._meta.sorted_fields}
    source_field_names = {f.name for f in source._meta.sorted_fields}
    fields_to_add = model_field_names - source_field_names
    fields_to_remove = source_field_names - model_field_names
    model_fields = model._meta.fields
    source_fields = source._meta.fields
    # The fields with a `change_fields` that replaces their index
    fields_to_reindex = {
        name
        for name in model_field_names & source_field_names
        if model_fields[name].unique != source_fields[name].unique
        and diff_field(model, source, name)
    }

    return [
        *diff_model_fields(model, source, **opts),
        *diff_model_indexes(
            model,
            source,
            fields_to_add=fields_to_add,
            fields_to_remove=fields_to_remove,
            fields_to_reindex=fields_to_reindex,
        ),
    ]


def diff_model_fields(model: TModelType, source: TModelType, **opts) -> list[str]:
    changes = []

    model_fields = {f.name for f in model._meta.sorted_fields}
    source_fields = {f.name for f in source._meta.sorted_fields}

    # Add fields
    fields_to_add = model_fields - source_fields
    if fields_to_add:
        fields = list(model_fields_gen(model, *fields_to_add))
        changes.append(create_fields(model, *fields, **opts))

    # Drop fields
    fields_to_remove = source_fields - model_fields
    if fields_to_remove:
        fields = list(model_fields_gen(source, *fields_to_remove))
        changes.append(drop_fields(model, *fields))

    # Change fields
    fields_to_change = model_fields - fields_to_add - fields_to_remove
    for field in model_fields_gen(model, *fields_to_change):
        diff = diff_field(model, source, field.name)
        if diff:
            changes.append(change_fields(model, (field, diff)))
            null = diff.pop("null", None)
            if null is not None:
                changes.append(change_not_null(model, field.name, null=null))

    return changes


def diff_field(model: TModelType, source: TModelType, name: str) -> dict:
    """Find the difference between a field of a model and the same field
    of its source.

    A model can declare the index of one column in the field (`index`,
    `unique`) or in `Meta.indexes`, and `migrator.add_index()` always marks
    the field. So the two are not a difference when the index is the same.
    """
    diff = compare_fields(model._meta.fields[name], source._meta.fields[name])
    if _field_indexes(model, name) == _field_indexes(source, name):
        diff.pop("index", None)
        diff.pop("unique", None)
    return diff


def _field_indexes(model: TModelType, name: str) -> set[bool]:
    """Whether each index of only the field `name` is unique."""
    return {
        bool(idx._unique)
        for idx in model._meta.fields_to_index()
        if [getattr(expr, "name", expr) for expr in idx._expressions] == [name]
    }


def diff_model_indexes(
    model: TModelType,
    source: TModelType,
    *,
    fields_to_add: set[str] | None = None,
    fields_to_remove: set[str] | None = None,
    fields_to_reindex: set[str] | None = None,
) -> list[str]:
    """Diff index sets between two model states.

    `fields_to_add` and `fields_to_remove` carry the field-level diff so we can
    skip emitting `add_index` / `drop_index` calls for indexes that peewee's
    `add_column` / `drop_column` will create or remove implicitly (single-column
    indexes on a field whose `index=True` or `unique=True` flag is set).
    Without this, autogenerated migrations duplicate the FK/unique auto-index
    and fail with "index already exists" on a fresh database.

    `fields_to_reindex` are the fields whose `unique` changes: the
    `change_fields` of the migration replaces their index, so it is skipped
    here for the same reason.
    """
    fields_to_add = fields_to_add or set()
    fields_to_remove = fields_to_remove or set()
    fields_to_reindex = fields_to_reindex or set()

    changes: list[str] = []

    model_indexes = model._meta.fields_to_index()
    source_indexes = source._meta.fields_to_index()

    model_indexes_names = {idx._name for idx in model_indexes}
    source_indexes_names = {idx._name for idx in source_indexes}

    # Drop indexes
    indexes_to_drop = source_indexes_names - model_indexes_names
    for name in sorted(indexes_to_drop):
        idx = next(i for i in source_indexes if i._name == name)
        if _is_implicit_field_index(idx, fields_to_remove | fields_to_reindex):
            continue
        changes.append(drop_index(idx))

    # Add indexes
    indexes_to_add = model_indexes_names - source_indexes_names
    for name in sorted(indexes_to_add):
        idx = next(i for i in model_indexes if i._name == name)
        if _is_implicit_field_index(idx, fields_to_add | fields_to_reindex):
            continue
        changes.append(add_index(idx))

    # Change indexes
    indexes_to_check = model_indexes_names & source_indexes_names
    for name in sorted(indexes_to_check):
        idx1 = next(idx for idx in model_indexes if idx._name == name)
        idx2 = next(idx for idx in source_indexes if idx._name == name)
        changed = idx1._unique != idx2._unique or sorted(idx1._expressions) != sorted(
            idx2._expressions
        )
        # What `change_fields` does: it drops the index of the field it
        # replaces, and makes the one of the field it is given
        dropped = _is_implicit_field_index(idx2, fields_to_reindex)
        made = _is_implicit_field_index(idx1, fields_to_reindex)
        if changed and not dropped:
            changes.append(drop_index(idx2))
        if (changed or dropped) and not made:
            changes.append(add_index(idx1))

    return changes


def _is_implicit_field_index(idx: pw.ModelIndex, field_names: set[str]) -> bool:
    """True if `idx` is a single-column index that peewee's `add_column` /
    `drop_column`, or the migrator's `change_fields`, will create or drop as a
    side effect of the field operation (i.e. the field has `index=True` or
    `unique=True` and is itself in `field_names`). Such indexes must not be
    re-emitted as separate `add_index` / `drop_index` calls.
    """
    exprs = idx._expressions  # type: ignore
    if len(exprs) != 1:
        return False
    expr = exprs[0]
    if not isinstance(expr, pw.Field):
        return False
    if expr.name not in field_names:
        return False
    return bool(getattr(expr, "index", False) or getattr(expr, "unique", False))


def diff_many(
    active: list[TModelType],
    source: list[TModelType],
    migrator: Migrator | None = None,
    *,
    reverse=False,
) -> list[str]:
    """Calculate changes for migrations from models2 to models1."""
    active = cast("list[TModelType]", pw.sort_models(active))  # type: ignore
    source = cast("list[TModelType]", pw.sort_models(source))  # type: ignore

    if reverse:
        active = list(reversed(active))
        source = list(reversed(source))

    active_map = {cast("str", m._meta.table_name): m for m in active}
    source_map = {cast("str", m._meta.table_name): m for m in source}

    changes: list[str] = []

    for name, model in active_map.items():
        if name not in source_map:
            continue
        changes.extend(diff_model(model, source_map[name], migrator=migrator))

    # Add models
    changes.extend(
        create_model(active_map[name], migrator=migrator)
        for name in [m for m in active_map if m not in source_map]
    )

    # Remove models
    changes.extend(
        remove_model(source_map[name])
        for name in [m for m in source_map if m not in active_map]
    )

    return changes


def model_to_code(model_type: TModelType, **kwargs) -> str:
    """Generate migrations for the given model."""
    template = "class {classname}(pw.Model):\n{fields}\n\n{meta}"
    meta = model_type._meta
    fields = INDENT + NEWLINE.join(
        [
            field_to_code(field, **kwargs)
            for field in meta.sorted_fields
            if not (isinstance(field, pw.PrimaryKeyField) and field.name == "id")
        ]
    )
    meta = INDENT + NEWLINE.join(
        filter(
            None,
            [
                "class Meta:",
                f'{INDENT}table_name = "{meta.table_name}"',
                f'{INDENT}schema = "{meta.schema}"' if meta.schema else "",
                (
                    f"{INDENT}primary_key = pw.CompositeKey{meta.primary_key.field_names!r}"
                    if isinstance(meta.primary_key, pw.CompositeKey)
                    else ""
                ),
                f"{INDENT}indexes = {meta.indexes!r}" if meta.indexes else "",
            ],
        )
    )

    return template.format(classname=model_type.__name__, fields=fields, meta=meta)


def create_model(model_type: TModelType, **kwargs) -> str:
    """Generate migrations to create model."""
    return "@migrator.create_model\n" + model_to_code(model_type, **kwargs)


def remove_model(model_type: TModelType, **kwargs) -> str:
    """Generate migrations to remove model."""
    meta = model_type._meta
    return "migrator.remove_model('%s')" % meta.table_name


def create_fields(model_type: TModelType, *fields: pw.Field, **kwargs) -> str:
    """Generate migrations to add fields."""
    meta = model_type._meta
    return "migrator.add_fields(%s'%s', %s)" % (
        NEWLINE,
        meta.table_name,
        NEWLINE
        + ("," + NEWLINE).join(
            [field_to_code(field, space=False, **kwargs) for field in fields]
        ),
    )


def drop_fields(model_type: TModelType, *fields: pw.Field | str) -> str:
    """Generate migrations to remove fields."""
    meta = model_type._meta
    field_names: tuple[str, ...] = tuple(
        repr(field.name) if isinstance(field, pw.Field) else repr(field)
        for field in fields
    )
    return "migrator.remove_fields('%s', %s)" % (meta.table_name, ", ".join(field_names))


def field_to_code(field: pw.Field, *, space: bool = True, **kwargs) -> str:
    """Generate field description."""
    col = Column(field)
    return col.get_field(" " if space else "")


def compare_fields(field1: pw.Field, field2: pw.Field) -> dict:
    """Find diffs between the given fields."""
    ftype1, ftype2 = find_field_type(field1), find_field_type(field2)
    if ftype1 != ftype2:
        return {"type": True}

    col1, col2 = (
        Column(field1, extra_parameters={"index": field1.index, "unique": field1.unique}),
        Column(field2, extra_parameters={"index": field2.index, "unique": field2.unique}),
    )
    params1, params2 = (
        col1.get_field_parameters(change=True),
        col2.get_field_parameters(change=True),
    )
    return dict(set(params1.items()) - set(params2.items()))


def change_fields(model_cls: TModelType, *fields: tuple[pw.Field, dict]) -> str:
    """Generate migrations to change fields."""
    meta = model_cls._meta
    return "migrator.change_fields('%s', %s)" % (
        meta.table_name,
        ("," + NEWLINE).join([field_to_code(f, space=False) for f, diff in fields]),
    )


def change_not_null(model_type: TModelType, name: str, *, null: bool) -> str:
    """Generate migrations."""
    meta = model_type._meta
    operation = "drop_not_null" if null else "add_not_null"
    return "migrator.%s('%s', %s)" % (operation, meta.table_name, repr(name))


def _index_fields(idx: pw.ModelIndex) -> list[str]:
    """Return field names for an index, raising on unsupported expressions."""
    fields = idx._expressions  # type: ignore
    names: list[str] = []
    for field in fields:
        if isinstance(field, pw.Field):
            names.append(field.name)
        elif isinstance(field, str):
            names.append(field)
        else:
            raise TypeError(
                "Cannot generate migration for index %r: unsupported expression %r"
                % (getattr(idx, "_name", None), field)
            )
    return names


def add_index(idx: pw.ModelIndex) -> str:
    """Generate migrations."""
    meta = idx._model._meta  # type: ignore
    unique = idx._unique  # type: ignore
    names = ", ".join(f"'{name}'" for name in _index_fields(idx))
    return f"migrator.add_index('{meta.table_name}', {names}, unique={unique})"


def drop_index(idx: pw.ModelIndex) -> str:
    """Generate migrations."""
    meta = idx._model._meta  # type: ignore
    names = ", ".join(f"'{name}'" for name in _index_fields(idx))
    return f"migrator.drop_index('{meta.table_name}', {names})"


def find_field_type(field: pw.Field) -> type[pw.Field]:
    ftype = type(field)
    if ftype.__module__ not in PW_MODULES:
        for cls in ftype.mro():
            if cls.__module__ in PW_MODULES:
                return cast("type[pw.Field]", cls)

    return ftype
