import typing as t
from collections.abc import Sequence
from fnmatch import fnmatch

from formidable.fields import Field
from markupsafe import Markup

from ..helpers.formatters import format_size
from . import errors


if t.TYPE_CHECKING:
    from ..storage import _Attachment


class AttachmentField(Field):
    """Field that turns a multipart file upload into a saved `Attachment`,
    suitable for assignment to a `ForeignKeyField` to `Attachment`.

    The field has a structured value composed of two sub-inputs:

    - `<name>[file]`: the file input (a `MultipartPart` on submit).
    - `<name>[_destroy]`: a hidden flag, "1" to explicitly clear the
      existing attachment without uploading a replacement. Mirrors the
      `_destroy` convention used by formidable's nested forms.

    The form parser collapses both into a single dict reqvalue
    `{"file": MultipartPart, "_destroy": "0"|"1"}`, which `set()`
    interprets:

    - **New upload**: builds `Attachment(upload)`, saves it, and purges the
      replaced original (if any) on `save()`.
    - **Explicit destroy** (no upload + _destroy=1): clears the FK and
      purges the original on `save()`.
    - **Neither**: preserves the bound attachment.

    Arguments:
        attachment_cls:
            the `Attachment` subclass to build for new uploads.
        max_size:
            optional max file size in bytes; if set, uploads with a
            `size` attribute exceeding this will fail validation.
            This is a soft limit independent of the hard limit set by the app.
        accept:
            optional list of allowed content type patterns; if set,
            uploads with a `content_type` attribute not matching one of these patterns will
            fail validation. E.g. `["image/*"]` allows `image/jpeg` and `image/png`
            but not `application/pdf`.
        required:
            whether a file upload is required (defaults to True).
        default:
            the default value for the field (defaults to None).
        messages:
            optional dict of error messages to override the defaults.
    """
    MESSAGES = errors.MESSAGES

    _original: "_Attachment | None" = None

    def __init__(
        self,
        attachment_cls: "type[_Attachment]",
        *,
        max_size: int | None = None,
        accept: Sequence[str] | None = None,
        required: bool = True,
        default: t.Any = None,
        messages: dict[str, str] | None = None,
        service_name: str = "",
    ):
        self.attachment_cls = attachment_cls
        self.max_size = max_size
        self.accept = [p.lower() for p in (accept or [])]
        self.service_name = service_name
        super().__init__(
            required=required,
            default=default,
            messages=messages,
        )

    def set(self, reqvalue, objvalue=None):
        self.error = None
        self.error_args = None
        self._error = None
        self._error_args = None

        # Remember the bound attachment so save() can purge it whenever the
        # form diverges from it (explicit remove or replacement upload).
        self._original = objvalue if isinstance(objvalue, self.attachment_cls) else None

        parts = self._unpack(reqvalue)
        file_part = parts.get("file")
        destroy = str(parts.get("_destroy") or "") == "1"

        # Browsers send an empty multipart part (filename="") for unselected
        # file inputs. Treat that as "no upload".
        if file_part is not None and not getattr(file_part, "filename", None):
            file_part = None

        if file_part is not None:
            self.value = file_part
        elif destroy:
            self.value = None
        else:
            self.value = objvalue

        if self.required and self.value is None:
            self._error = errors.REQUIRED

    def validate_value(self) -> bool:
        """Validates the uploaded file's size and content type if possible, but
        doesn't fail if those attributes aren't available (e.g. when manually
        assigning an `Attachment` in code rather than via upload).
        """
        if self.value is None:
            return True

        if self.max_size is not None:
            size = getattr(self.value, "size", None)
            if size is not None and size > self.max_size:
                self.error = errors.FILE_TOO_LARGE
                self.error_args = {"max_size": format_size(self.max_size)}
                return False

        if self.accept:
            content_type = getattr(self.value, "content_type", None)
            if content_type is not None:
                content_type = content_type.lower()
                for ct in self.accept:
                    if fnmatch(content_type, ct):
                        break
                else:
                    self.error = errors.INVALID_CONTENT_TYPE
                    self.error_args = {"accept": self.accept}
                    return False

        return True

    def save(self) -> "_Attachment | None":
        original = self._original

        # Existing Attachment preserved across an edit - same row, no purge.
        if isinstance(self.value, self.attachment_cls):
            return self.value

        # No upload (and possibly explicit purge) - clear the FK and purge
        # the original if there was one.
        if self.value is None:
            if original is not None:
                original.purge_later()
            return None

        # Fresh upload - build, save, and purge the replaced original.
        attachment = self.attachment_cls(self.value, service_name=self.service_name)
        attachment.save()
        if original is not None:
            try:
                original.purge_later()
            except ValueError:
                pass
        return attachment

    # --- Rendering helpers ---

    def file_input(self, **attrs: t.Any) -> str:
        """Renders the `<input type="file" name="<field>[file]">` element.

        File inputs ignore the `value` attribute (browsers can't pre-fill
        them for security), so we omit it even when the field has a bound
        Attachment.
        """
        attributes: dict[str, t.Any] = {
            "type": "file",
            "id": self.id,
            "name": f"{self.name}[file]",
        }
        # Don't force `required` when an existing attachment is already bound:
        # the user shouldn't have to re-upload to submit the form.
        if self.required and not isinstance(self.value, self.attachment_cls):
            attributes["required"] = True
        if self.error:
            attributes["aria-invalid"] = "true"
            attributes["aria-errormessage"] = f"{self.id}-error"
        attributes.update(attrs)
        attr_str = self._render_html_attrs(attributes)
        return Markup(f"<input {attr_str} />")

    def destroy_input(self, **attrs: t.Any) -> str:
        """Renders the hidden `<input name="<field>[_destroy]" value="0">`
        flag the JS toggles to "1" when the user clicks Remove. Matches
        the `_destroy` convention used by formidable's nested forms.
        """
        attributes: dict[str, t.Any] = {
            "type": "hidden",
            "name": f"{self.name}[_destroy]",
            "value": "0",
            **attrs,
        }
        attr_str = self._render_html_attrs(attributes)
        return Markup(f"<input {attr_str} />")

    # --- Private ---

    def _unpack(self, reqvalue: t.Any) -> dict[str, t.Any]:
        """Normalize `reqvalue` into a dict of named sub-parts.

        Returns a dict so subclasses can extend the structured value with
        additional sub-inputs (alt text, sort order, crop coords, …) by
        rendering them under bracketed names like `<field>[alt]` and
        reading `parts["alt"]` in their override of `set()`.

        Tolerates the legacy bare-MultipartPart shape so a plain
        `name="<field>"` file input still works.
        """
        if reqvalue is None:
            return {}
        if isinstance(reqvalue, dict):
            return dict(reqvalue)
        # Bare upload - no `_destroy` (or other) channels available.
        return {"file": reqvalue}
