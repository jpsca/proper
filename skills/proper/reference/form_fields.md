---
title: Form Field Types
description: Reference: every `proper.forms` field with its options and an example (Text, Boolean, Integer, Float, File, Attachment, RichText, JSON, List, Date, DateTime, Time, Email, URL, Slug, FormField, NestedForms)
last_verified: 2026-11-07
sources:
  - src/proper/forms
---

# Form Field Types

Read this to confirm the options of one field. How forms work (constructor, validation, saving, rendering) is in [forms.md](../forms.md); the table that picks a field by use case is in [forms.md, Fields](../forms.md#fields).

## Table of Contents

- [TextField](#textfield)
- [BooleanField](#booleanfield)
- [IntegerField](#integerfield)
- [FloatField](#floatfield)
- [FileField](#filefield)
- [AttachmentField](#attachmentfield)
- [RichTextField](#richtextfield)
- [JSONField](#jsonfield)
- [ListField](#listfield)
- [DateField](#datefield)
- [DateTimeField](#datetimefield)
- [TimeField](#timefield)
- [EmailField](#emailfield)
- [URLField](#urlfield)
- [SlugField](#slugfield)
- [FormField (Sub-form)](#formfield-sub-form)
- [NestedForms (One-to-Many)](#nestedforms-one-to-many)


## TextField

```python
f.TextField(
    *, required=True, default=None, strip=True,
    min_length=None, max_length=None, pattern=None, one_of=None, messages=None
    label=None,
)
```

The `default` can be a static value or a callable (called at form instantiation time). This applies to all field types.

IMPORTANT: When using a `TextField`, review if an `EmailField` or `URLField` would be better choices.

## BooleanField

```python
f.BooleanField(*, required=False, default=None, messages=None, label=None)
```

Also exported as `f.BoolField` — same class, just a shorter alias.

Handles browser checkbox behavior:

- If not checked: the browser sends nothing, and the field keeps the object's value, else the default, else `False`. To make unchecking work on an edit form, `checkbox()` renders a hidden input with value `"0"` before the checkbox; add it yourself if you write the HTML by hand
- If checked: the browser sends the `value` attribute (or an empty string) → becomes `True`
- A string value in the `FALSE_VALUES` tuple (case-insensitive: `"false"`, `"0"`, `"no"`) → becomes `False`
- Any other value, including an empty string → becomes `True`
- `required=True` means the value must be `True` (useful for "accept terms" checkboxes)

## IntegerField

```python
f.IntegerField(
    *, required=True, default=None,
    gt=None, gte=None, lt=None, lte=None, multiple_of=None, one_of=None, messages=None
    label=None,
)
```

## FloatField

Same signature as IntegerField, converts to float.

## FileField

```python
f.FileField(*, required=True, default=None, messages=None, label=None)
```

Does not process or upload files. The form only validates that a value was provided (when required). Handle the actual file data in the controller:

```python
def create(self):
    upload = self.params.get("avatar")
    # Process the upload in the controller, not the form
```

## AttachmentField

```python
f.AttachmentField(
    attachment_cls,
    *, max_size=None, accept=None,
    required=True, default=None, messages=None,
    service_name="",
)
```

For models with a `ForeignKeyField(Attachment, null=True)` column. Unlike `FileField`, this field handles the upload itself: `form.save()` writes the file through the storage service, inserts the attachment row, and assigns the FK on the bound model — no controller plumbing needed. See [storage.md](../storage.md) for the Attachment model.

```python
from proper import forms as f

from myapp.models import Attachment, Book


class BookForm(f.Form):
    class Meta:
        orm_cls = Book

    title = f.TextField()
    cover = f.AttachmentField(Attachment, service_name="public", required=False)
```

```python
def update(self):
    book = self.form.save()
    # cover upload, replacement, and removal are all handled by the field.
    self.response.redirect_to("Book.show", book)
```

#### Structured value

The field's reqvalue is a dict with two keys, produced by two HTML inputs sharing the field's bracketed name:

| Key | Source input | Purpose |
|---|---|---|
| `file` | `<input type="file" name="<field>[file]">` | The upload (a `MultipartPart`). |
| `_destroy` | `<input type="hidden" name="<field>[_destroy]">` | `"1"` to clear the existing attachment without uploading a replacement. Mirrors the `_destroy` convention used by `NestedForms`. |

Behavior matrix:

| `file` present | `_destroy` | Action |
|---|---|---|
| yes | (any) | New attachment is saved; the previous one (if any) is purged via `purge_later()`. |
| no | `"1"` | FK is cleared; the existing attachment is purged via `purge_later()`. |
| no | `"0"` / absent | Bound attachment is preserved. |

#### Render helpers

```html+jinja
{{ form.cover.file_input(accept="image/*") }}
{{ form.cover.destroy_input() }}
```

- `file_input(**attrs)` renders `<input type="file" name="<field>[file]">`. The `value` attribute is intentionally omitted (browsers ignore it on file inputs). When the field has a bound attachment, `required` is dropped so the user doesn't have to re-upload to submit.
- `destroy_input(**attrs)` renders `<input type="hidden" name="<field>[_destroy]" value="0">`. Toggle the value to `"1"` from JavaScript when offering a "Remove" button.

#### Drop-in image input

The `proper install storage` blueprint installs an image-input component that wires this together — preview state for existing attachments, drag-and-drop, replace/remove with destroy-flag toggling. Use it like:

```html+jinja
{#import "image_input.jx" as ImageInput #}

<ImageInput field={{ form.cover }} />
```

#### Validation

Two optional constraints run during `form.validate()`:

| Argument | Effect | Error code | Error args |
|---|---|---|---|
| `max_size=N` | Reject uploads whose `size` (in bytes) exceeds `N`. The boundary is inclusive — `size == max_size` passes. | `errors.FILE_TOO_LARGE` | `{"max_size": "<formatted size>"}` (rendered through `format_size`, e.g. `"1 KB"`) |
| `accept=[...]` | Reject uploads whose `content_type` doesn't match any of the listed glob patterns. Matching is via `fnmatch`, case-insensitive. `["image/*"]` accepts `image/png`, `image/jpeg`, etc.; `["application/pdf"]` is a literal match. | `errors.INVALID_CONTENT_TYPE` | `{"accept": [...]}` |

Both checks read attributes off the field's value via `getattr(..., None)` and skip silently when the attribute is missing. A bound `Attachment` has no `size` attribute (it stores `byte_size`), so `max_size` is skipped for it; it does have `content_type`, so `accept` is checked against an existing attachment too: tightening `accept` can make existing records fail validation until the file is replaced.

`max_size` is checked before `accept`; if both fail on the same upload, only the size error surfaces. Passing `accept=None` or `accept=[]` disables the check entirely.

```python
class BookForm(f.Form):
    class Meta:
        orm_cls = Book

    cover = f.AttachmentField(
        Attachment,
        max_size=5 * 1024 * 1024,            # 5 MB
        accept=["image/*"],                  # any image type
        service_name="public",
        required=False,
    )
```

`accept` patterns mirror the syntax of the HTML `accept` attribute on `<input type="file">`, so the Python list and the rendered `accept="..."` string can use the same patterns.

`max_size` is a soft, application-level limit, checked after the request is parsed. The hard ceiling for uploads is `MAX_CONTENT_LENGTH`, the largest request body the app reads (a larger one is refused before it is read); `MAX_FORM_PART_SIZE` limits only the fields that aren't files. Use `max_size` for per-field business rules; configure `MAX_CONTENT_LENGTH` for the global ceiling.

#### Subclass extension

`AttachmentField._unpack(reqvalue)` returns the raw parts dict. Subclasses can extend with extra sub-inputs (alt text, sort order, crop coords) by rendering them under bracketed names like `<field>[alt]` and reading `parts["alt"]` in their override of `set()`.

## RichTextField

```python
f.RichTextField(*, required=False, **textfield_kwargs)  # default, min_length, max_length, pattern, one_of, label, messages; strip is fixed to False and can't be passed
```

Form-layer adapter for a model `RichTextField` column. Defaults to `required=False` (most rich-text bodies are optional) and `strip=False` (whitespace is meaningful in HTML).

When the form is bound to an existing record, the field coerces the model's `RichTextDocument` to its `to_editor_html()` representation (the stored HTML with each `<proper-attachment>` tag's attributes rebuilt from the attachment row) so the editor re-loads the original HTML — not the plain-text view that `str(RichTextDocument)` returns. See [rich_text.md](../rich_text.md) for the model side and editor integration.

## JSONField

```python
f.JSONField(*, required=True, default=None, messages=None)
```

Captures JSON input from a form. Accepts:

- A dict (passed through unchanged).
- An object with a `to_dict()` method (called).
- A JSON-encoded string (parsed). Invalid JSON raises an `INVALID_JSON` validation error.
- An empty/whitespace string → `None`.

Useful for hidden inputs that round-trip structured data, or for form fields backing a `JSONField` model column. The rendered string value is the JSON-encoded form of the current dict.

## ListField

The rendered `name` gets a `[]` suffix (`tags[]`).

```python
f.ListField(
    type=None, *, strict=False, required=True, default=[],
    min_items=None, max_items=None, one_of=None, messages=None
    label=None,
)
```

For multiple values (e.g. `<select multiple>`, checkboxes). `type` is a callable to cast items (e.g. `int`). When `strict=False` (default), items that fail casting are silently skipped. When `strict=True`, a casting error raises an exception. An empty submission results in `[]`.

## DateField

```python
f.DateField(
    format='%Y-%m-%d', *, required=True, default=None,
    after_date=None, before_date=None, past_date=False, future_date=False,
    offset=0, one_of=None, messages=None
    label=None,
)
```

Converts to `datetime.date`. `offset` is timezone offset in hours for past/future checks. `after_date` and `before_date` accept either a `datetime.date` object or a date string.

## DateTimeField

```python
f.DateTimeField(
    format='%Y-%m-%dT%H:%M:%S', *, required=True, default=None,
    after_date=None, before_date=None, past_date=False, future_date=False,
    offset=0, one_of=None, messages=None
    label=None,
)
```

## TimeField

```python
f.TimeField(
    *, required=True, default=None,
    after_time=None, before_time=None, past_time=False, future_time=False,
    offset=0, one_of=None, messages=None
    label=None,
)
```

Unlike DateField and DateTimeField, TimeField has no `format` parameter — it parses time strings automatically.

## EmailField

```python
f.EmailField(
    *, required=True, default=None,
    check_dns=False, allow_smtputf8=False, strict=True, one_of=None, messages=None
    label=None,
)
```

Requires the `email-validator` package, which Proper does not install: run `uv add email-validator` in the app before using this field, or every non-empty value raises `ImportError`. Normalizes the domain to lowercase with Unicode NFC normalization, and converts fullwidth/halfwidth characters.

| Option | Description |
|--------|-------------|
| `check_dns` | If `True`, makes DNS queries to verify the domain can receive mail |
| `allow_smtputf8` | Accept non-ASCII characters in the local part (before the @-sign). Requires SMTPUTF8 support along the mail route |
| `strict` | If `True`, validates that the local part is at most 64 characters long |

## URLField

```python
f.URLField(*, required=True, default=None, schemes=None, one_of=None, messages=None, label=None)
```

Default schemes: `["http", "https"]`. Normalizes the domain with UTS-46 (lowercasing, NFC normalization). Note that even if the format is valid, the URL is not guaranteed to be real — the purpose is to catch typing mistakes.

## SlugField

```python
f.SlugField(*, required=True, default=None, slugify=<default>, one_of=None, messages=None, label=None)
```

Auto-slugifies input. The default slugify function handles Latin-based characters but removes most non-Latin scripts (Cyrillic, Arabic, Hebrew, Hindi, etc.). Provide a custom `slugify` callable if you need broader Unicode support.

## FormField (Sub-form)

```python
f.FormField(FormClass, *, required=True, default=None, label=None)
```

Embeds another form as a single nested object. Access the sub-form instance via `field.form` (e.g., `form.settings.form.locale` in templates). On save:

- If the sub-form has `orm_cls`: creates/updates an ORM object (useful for ForeignKey relationships)
- If the sub-form has no `orm_cls`: returns a plain dict (useful for JSON fields)

```python
class SettingsForm(f.Form):
    locale = f.TextField(default="en_us")
    timezone = f.TextField(default="utc")

class ProfileForm(f.Form):
    name = f.TextField()
    settings = f.FormField(SettingsForm)

# form.save() returns: {"name": "...", "settings": {"locale": "...", "timezone": "..."}}
```

## NestedForms (One-to-Many)

```python
f.NestedForms(FormClass, *, min_items=None, max_items=None, default=None, allow_delete=False, label=None)
```

Dynamic add/remove of sub-forms. Equivalent to a one-to-many relationship. Deletion is disabled by default — set `allow_delete=True` to enable it.

```python
class AddressForm(f.Form):
    class Meta:
        orm_cls = Address
    kind = f.TextField()
    street = f.TextField()

class PersonForm(f.Form):
    class Meta:
        orm_cls = Person
    name = f.TextField()
    addresses = f.NestedForms(AddressForm, allow_delete=True)
```

On save:

- If the nested form has `orm_cls`: returns a list of ORM objects
- If the nested form has no `orm_cls`: returns a list of dicts
- Only nested forms can delete objects; FormField cannot delete

**Key properties/methods:**

- `field.forms` — list of sub-form instances
- `field.empty_form` — an empty sub-form instance, specifically for use in a `<template>` tag for JS-powered dynamic addition
- `field.build(n)` — pre-populate with `n` empty forms

**Template:**

```html+jinja
{% for address in form.addresses.forms %}
<div class="nestedform">
  {{ address.hidden_tags() }}
  {{ address.kind.label("Kind") }}
  {{ address.kind.text_input() }}
  {{ address.street.label("Street") }}
  {{ address.street.text_input() }}
</div>
{% endfor %}
```

`hidden_tags()` renders `_id` (primary key) and `_destroy` (deletion marker) hidden inputs. These are required for each nested form. The `_id` field is only rendered when the form has an existing object; the `_destroy` field is only rendered when `allow_delete=True`.

The `_id` hidden field is secure — its value is ignored if it doesn't match one of the objects used to instantiate the form, preventing users from updating objects they aren't authorized to modify.

If the form data contains `_destroy` with a non-empty value, the object will be deleted.

**Input naming convention:** Nested form inputs use the format `fieldname[INDEX][subfield]`, e.g., `addresses[0][street]`. The index numbers are not significant and don't represent order — they just need to be unique per sub-form.

#### Dynamic Add/Remove with JavaScript

To enable dynamic adding and removing of nested forms in the browser, use the `nestedform.js` script with these data attributes:

1. Add `data-nestedform` to the wrapping form element
2. Give each sub-form wrapper the CSS class `nestedform`
3. Add a remove button with `data-nestedform-remove` inside each sub-form
4. Add a `<template data-nestedform-template>` **inside** the `data-nestedform` element, using `field.empty_form` to render the template content
5. Add a `data-nestedform-target` element where new sub-forms should be inserted
6. Add an add button with `data-nestedform-add`

Use a Jinja macro to avoid duplicating the sub-form markup between the loop and the template:

```html+jinja
{% macro render_address(form, label) -%}
<div class="nestedform">
  {{ form.hidden_tags() }}
  <div class="field">
    {{ form.kind.label(label) }}
    {{ form.kind.text_input() }}
    <button type="button" data-nestedform-remove title="Remove">&times;</button>
  </div>
  {{ form.street.label("Street") }}
  {{ form.street.text_input() }}
</div>
{%- endmacro %}

<form method="post" data-nestedform>
  {% for address in form.addresses.forms %}
    {{ render_address(address, "Address") }}
  {% endfor %}

  <template data-nestedform-template>
    {{ render_address(form.addresses.empty_form, "New Address") }}
  </template>

  <div data-nestedform-target></div>
  <button type="button" data-nestedform-add>Add Address</button>
  <button type="submit">Save</button>
</form>
```
