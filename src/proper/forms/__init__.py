import json

from formidable.fields import (
    BooleanField,
    BoolField,
    DateField,
    DateTimeField,
    EmailField,
    Field,
    FileField,
    FloatField,
    FormField,
    IntegerField,
    ListField,
    NestedForms,
    SlugField,
    TextField,
    TimeField,
    URLField,
)
from formidable.form import Form

from . import errors
from .attachment_field import AttachmentField
from .errors import MESSAGES
from .rich_text_field import RichTextField


__all__ = (
  "AttachmentField",
  "BooleanField",
  "BoolField",
  "DateField",
  "DateTimeField",
  "EmailField",
  "Field",
  "FileField",
  "FloatField",
  "FormField",
  "IntegerField",
  "JSONField",
  "ListField",
  "NestedForms",
  "RichTextField",
  "SlugField",
  "TextField",
  "TimeField",
  "URLField",
  "Form",
  "errors",
  "MESSAGES",
)

class JSONField(Field):
    """
    A JSON field for forms.
    This field is used to capture JSON input from users.

    Args:
        required:
            Whether the field is required. Defaults to `True`.
        default:
            Default value for the field. Can be a static value or a callable.
            Defaults to `None`.
        messages:
            Dictionary of error codes to custom error message templates.
            These override the default error messages for this specific field.
            Example: {"required": "This field cannot be empty"}.
    """
    def __init__(
        self,
        *,
        required: bool = True,
        default: dict | str | None = None,
        messages: dict[str, str] | None = None,
    ):
        if isinstance(default, str):
            default = self.filter_value(default)
        super().__init__(required=required, default=default, messages=messages)

    def filter_value(self, value: str | None) -> dict | None:
        """
        Convert the value to a dict.
        """
        if value is None:
            return None
        if hasattr(value, "to_dict"):
            return value.to_dict()  # type: ignore
        if isinstance(value, dict):
            return value
        if isinstance(value, str) and not value.strip():
            return None

        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            raise ValueError(errors.INVALID_JSON) from None

    def _str_value(self) -> str:
        if self.value is None:
            return ""
        return json.dumps(self.value)
