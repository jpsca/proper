from peewee import TextField

from . import jsonplus


__all__ = ("JSONField", )


class JSONField(TextField):
    field_type = "JSON"

    def db_value(self, value):
        if value is not None:
            return jsonplus.dumps(
                value,
                ensure_ascii=getattr(
                    self.model._meta.database, "json_ensure_ascii", True
                ),
                indent=2
                if getattr(self.model._meta.database, "json_use_detailed", False)
                else 0,
            )

    def python_value(self, value):
        if value is not None:
            return jsonplus.loads(value)
