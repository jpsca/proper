---
title: Formidable Forms
description: Form validation library — field definitions, validators, ORM integration, rendering
last_verified: 2026-06-03
---

# Formidable Forms

Formidable is a form validation library. Forms contain field definitions, handle validation, and orchestrate saving. Import as `from proper import forms as f`. Proper re-exports every formidable primitive under `proper.forms` and adds Proper-specific fields (e.g. `AttachmentField`), so a single import covers everything you need.

## Table of Contents

- [Defining Forms](#defining-forms)
- [Form Constructor](#form-constructor)
- [Form API](#form-api)
- [Fields](#fields)
- [Field Types](#field-types)
- [ORM Integration](#orm-integration)
- [Custom Error Messages](#custom-error-messages)


## Defining Forms

```python
from proper import forms as f

class TeamForm(f.Form):
    name = f.TextField()
    description = f.TextField(required=False)
```

Field names must be valid Python identifiers, cannot start with `_`, and cannot be named `get_errors`, `hidden_tags`, `save`, `validate`, or `after_validate` (these are reserved). Fields named `is_valid` or `is_invalid` are also rejected if defined as `Field` instances.

### Form Inheritance

```python
class BasePostForm(f.Form):
    title = f.TextField()
    content = f.TextField()

class ModeratorPostForm(BasePostForm):
    published_at = f.DateTimeField()
    layout = f.TextField(one_of=["post", "featured"])
```

Subclass fields override parent fields with the same name. Limit to two levels of inheritance (plus a base form) to keep things debuggable; favor composition for reusable snippets.


## Form Constructor

```python
Form(
    reqdata=None,       # Request data (e.g. self.params from controller)
    object=None,        # Model instance or dict for initial values
    *,
    name_format='{name}',  # Format string for field names
    messages=None,          # Custom error messages dict
)
```

The `reqdata` argument should be a dictionary-like object that can have multiple values per key (e.g., `self.params` from a Proper controller). For testing, you can use a dict of `key: [value1, value2, ...]`.

The `object` argument can be a model instance or a plain `key: value` dictionary. It provides initial values for the form fields.

Messages passed here are inherited by `NestedForms` and `FormField` sub-forms. However, if those sub-forms define their own `messages`, theirs take precedence.

### Instantiation Patterns

```python
form = MyForm()                      # Empty form (for "new" page)
form = MyForm(request_data)          # After form submission (for "create")
form = MyForm({}, object)            # Pre-filled from object (for "edit" page)
form = MyForm(request_data, object)  # Submission + object (for "update")
```

Request data values take precedence over object data. When no data is provided (pattern 1), fields are `None` and validation will fail, but the form can still be rendered.

You can also pass messages at instantiation time for runtime localization:

```python
form = MyForm(reqdata, objdata, messages=MESSAGES[user.locale])
```


## Form API

### Validation

```python
form.is_valid      # Property: triggers validation, returns bool
form.is_invalid    # Property: opposite of is_valid
form.validate()    # Manually trigger validation, returns bool
```

`is_valid` and `is_invalid` trigger validation on first access and cache the result. Subsequent accesses return the cached value without re-validating.

### Errors

```python
form.get_errors()   # Returns dict of {field_name: error_code} for all fields with errors
```

Useful for API/JSON error responses.

### Saving

```python
data = form.save(**extra)
```

The return value and persistence behavior depend on how the form was constructed:

| Constructed with | Returns | Persists? |
|---|---|---|
| No `orm_cls`, no `object` | A plain dict of field values | No |
| An `object` (plain dict) | The same dict, updated with field values | No |
| An `object` (ORM model) | The same instance, updated with field values | **Yes** — calls `object.save()` |
| `orm_cls` set, no `object` | A new model instance | **Yes** — created via `orm_cls.create(...)` |

For ORM-bound forms the field-save loop and the object save run inside a single transaction (see [ORM Integration](#orm-integration)). No follow-up `instance.save()` is needed.

Extra kwargs are set on the result before returning — useful for values that shouldn't be editable form fields:

```python
photo = self.form.save(user_id=current.user.id)
# photo is already persisted when Meta.orm_cls is set
```

Only call `save()` after validation passes (`form.is_valid`). Calling `save()` on an invalid form raises `ValueError`.

### Form-level Validation

```python
class PasswordChangeForm(f.Form):
    password1 = f.TextField()
    password2 = f.TextField()

    def after_validate(self) -> bool:
        if self.password1.value != self.password2.value:
            self.password2.error = "passwords_mismatch"
            return False
        return True
```

Called after individual field validations. Must return `True`/`False`. Set `field.error` to indicate errors.

IMPORTANT: Before writing a custom validator, check if one of the built-in validation can be used instead. For example, the `one_of` argument can validate the selected value is one of a predefined list.

## Fields

Fields are declared as class attributes. When a form is instantiated, a copy of each field is made — each field instance maintains its own data and settings.

When adding explicit fields, pick the right type:                                                                                    
                                                                                                                                     
| Field | Use for | Key options |
|-------|---------|-------------|
| `f.TextField()` | Short/long strings | `min_length`, `max_length`, `pattern`, `one_of` |
| `f.EmailField()` | Email addresses | `check_dns` |
| `f.URLField()` | URLs | `schemes` |
| `f.SlugField()` | URL slugs | auto-slugifies input |
| `f.IntegerField()` | Integers | `gt`, `gte`, `lt`, `lte`, `multiple_of` |
| `f.FloatField()` | Decimals | same as IntegerField |
| `f.BooleanField()` | Checkboxes | `required=False` by default |
| `f.DateField()` | Dates | `after_date`, `before_date`, `past_date`, `future_date` |
| `f.DateTimeField()` | Date + time | same as DateField |
| `f.TimeField()` | Time only | `after_time`, `before_time` |
| `f.FileField()` | File uploads | validation only; handle file in controller |
| `f.AttachmentField(A)` | File upload bound to a `ForeignKey(Attachment)` | `max_size`, `accept`; saves the upload, replaces or destroys the existing attachment automatically |
| `f.ListField()` | Multi-select/checkboxes | `type`, `min_items`, `max_items` |
| `f.FormField(F)` | Nested object | embeds another form |
| `f.NestedForms(F)` | One-to-many | `min_items`, `max_items`, `allow_delete` |

### Processing Order

For each field, the processing order is:

1. **Filter** — transforms the raw input value
2. **Built-in validators** — checks required, type casting, constraints
3. **Custom validator** — your `validate_fieldname` method

### Custom Filters and Validators

**Filters** transform input data. Named `filter_fieldname`:

```python
class MyForm(f.Form):
    name = f.TextField()

    def filter_name(self, value):
        if value is None:
            return value
        return value.lower()
```

Always check for `None` before operating on the value — filters receive `None` when the field has no input.

Note: For `NestedForms` and `FormField`, the custom filter signature is different — it receives `(reqvalue, objvalue)` and must return a `(reqvalue, objvalue)` tuple.

**Validators** check if value is valid. Named `validate_fieldname`. Raise `ValueError` with an error code. Must return the value:

```python
class MyForm(f.Form):
    name = f.TextField()

    def validate_name(self, value):
        if "e" not in (value or ""):
            raise ValueError("invalid")
        return value
```

### Field Attributes

| Attribute | Description |
|-----------|-------------|
| `field.id` | Auto-generated ID for connecting labels to inputs (accessibility) |
| `field.name` | HTML form name. Same as declared name for simple forms; prefixed for nested forms (e.g., `addresses[0][street]`) |
| `field.value` | Current value (may be `None`) |
| `field.error` | Error code string or `None` |
| `field.error_args` | Optional dict of extra error details for message placeholders |
| `field.error_message` | Human-readable error from messages dict |

### Render Methods

All render methods accept `**attrs` for additional HTML attributes. Use trailing underscore for Python reserved words: `class_="text-sm"` renders as `class="text-sm"`.

Fields with the `required` option automatically add the `required` HTML attribute. Fields with errors automatically add `aria-invalid="true"` and `aria-errormessage` attributes.

| Method | Renders | Notes |
|--------|---------|-------|
| `field.label(text=None, **attrs)` | `<label>` element | If `text` is `None`, uses the field name |
| `field.error_tag(**attrs)` | `<div class="field-error">` | Only rendered if error exists. Custom `class_` replaces default |
| `field.text_input(**attrs)` | `<input type="text">` | |
| `field.textarea(**attrs)` | `<textarea>` | |
| `field.select(options, **attrs)` | `<select>` | Options as `[(value, text), ...]`. Matching values get `selected`. Automatically adds `multiple` for ListField |
| `field.checkbox(**attrs)` | `<input type="checkbox">` | Checked when field value is truthy |
| `field.radio(radio_value, **attrs)` | `<input type="radio">` | Checked when `radio_value` matches field value |
| `field.file_input(**attrs)` | `<input type="file">` | Use `accept="image/*"` to restrict file types |
| `field.hidden_input(**attrs)` | `<input type="hidden">` | |
| `field.password_input(**attrs)` | `<input type="password">` | |
| `field.number_input(**attrs)` | `<input type="number">` | Shows spinner, numeric keypad on mobile |
| `field.email_input(**attrs)` | `<input type="email">` | |
| `field.url_input(**attrs)` | `<input type="url">` | |
| `field.date_input(**attrs)` | `<input type="date">` | |
| `field.datetime_input(**attrs)` | `<input type="datetime-local">` | |
| `field.time_input(**attrs)` | `<input type="time">` | |
| `field.color_input(**attrs)` | `<input type="color">` | Opens color picker |
| `field.search_input(**attrs)` | `<input type="search">` | Line-breaks removed, may show clear icon |
| `field.tel_input(**attrs)` | `<input type="tel">` | Shows telephone keypad on mobile |
| `field.range_input(**attrs)` | `<input type="range">` | Use with `min` and `max` attrs |
| `field.month_input(**attrs)` | `<input type="month">` | |
| `field.week_input(**attrs)` | `<input type="week">` | |



### Template Usage

```html+jinja
<form method="post">
  <div class="field">
    {{ form.name.label("Name") }}
    {{ form.name.text_input() }}
    {{ form.name.error_tag() }}
  </div>

  <div class="field">
    {{ form.description.label("Description") }}
    {{ form.description.textarea() }}
    {{ form.description.error_tag() }}
  </div>

  <button type="submit">Save</button>
</form>
```

### Manual HTML Alternative

You can write form HTML manually using field attributes instead of the render helpers. This is useful when you need full control over the markup:

```html+jinja
<label for="{{ form.title.id }}">Title</label>
<input type="text"
  id="{{ form.title.id }}"
  name="{{ form.title.name }}"
  value="{{ form.title.value or '' }}"
  {% if form.title.error %}aria-invalid="true"{% endif %}
/>
{% if form.title.error %}
  <span class="field-error">{{ form.title.error_message }}</span>
{% endif %}
```


## Field Types

### TextField

```python
f.TextField(
    *, required=True, default=None, strip=True,
    min_length=None, max_length=None, pattern=None, one_of=None, messages=None
)
```

The `default` can be a static value or a callable (called at form instantiation time). This applies to all field types.

IMPORTANT: When using a `TextField`, review if an `EmailField` or `URLField` would be better choices.

### BooleanField

```python
f.BooleanField(*, required=False, default=None, messages=None)
```

Also exported as `f.BoolField` — same class, just a shorter alias.

Handles browser checkbox behavior:

- If not checked: the browser doesn't send the field at all → becomes `False`
- If checked: the browser sends the `value` attribute (or an empty string) → becomes `True`
- A string value in the `FALSE_VALUES` tuple (case-insensitive: `"false"`, `"0"`, `"no"`) → becomes `False`
- Any other value, including an empty string → becomes `True`
- `required=True` means the value must be `True` (useful for "accept terms" checkboxes)

### IntegerField

```python
f.IntegerField(
    *, required=True, default=None,
    gt=None, gte=None, lt=None, lte=None, multiple_of=None, one_of=None, messages=None
)
```

### FloatField

Same signature as IntegerField, converts to float.

### FileField

```python
f.FileField(*, required=True, default=None, messages=None)
```

Does not process or upload files. The form only validates that a value was provided (when required). Handle the actual file data in the controller:

```python
def create(self):
    upload = self.request.form.get("avatar")
    # Process the upload in the controller, not the form
```

### AttachmentField

```python
f.AttachmentField(
    attachment_cls,
    *, max_size=None, accept=None,
    required=True, default=None, messages=None,
    service_name="",
)
```

For models with a `ForeignKeyField(Attachment, null=True)` column. Unlike `FileField`, this field handles the upload itself: `form.save()` writes the file through the storage service, inserts the attachment row, and assigns the FK on the bound model — no controller plumbing needed. See [storage.md](storage.md) for the Attachment model.

```python
from proper import forms as f

from [[app_name]].models import Attachment, Book


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

Both checks read attributes off the field's value via `getattr(..., None)` and skip silently when the attribute is missing. That matters when the field is bound to an existing `Attachment` (manual assignment in code, not an upload) — those don't carry an upload `.size` or `.content_type`, and pre-existing data shouldn't be re-validated against current rules.

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

`max_size` is a soft, application-level limit on top of the framework's hard `MAX_FORM_PART_SIZE` (which protects the request parser from runaway uploads). Use `max_size` for per-field business rules; configure `MAX_FORM_PART_SIZE` for the global ceiling.

#### Subclass extension

`AttachmentField._unpack(reqvalue)` returns the raw parts dict. Subclasses can extend with extra sub-inputs (alt text, sort order, crop coords) by rendering them under bracketed names like `<field>[alt]` and reading `parts["alt"]` in their override of `set()`.

### RichTextField

```python
f.RichTextField(*, required=False, default=None, messages=None, **kwargs)
```

Form-layer adapter for a model `RichTextField` column. Defaults to `required=False` (most rich-text bodies are optional) and `strip=False` (whitespace is meaningful in HTML).

When the form is bound to an existing record, the field coerces the model's `RichTextDocument` to its `to_html()` representation so the editor re-loads the original HTML — not the plain-text view that `str(RichTextDocument)` returns. See [rich_text.md](rich_text.md) for the model side and editor integration.

### JSONField

```python
f.JSONField(*, required=True, default=None, messages=None)
```

Captures JSON input from a form. Accepts:

- A dict (passed through unchanged).
- An object with a `to_dict()` method (called).
- A JSON-encoded string (parsed). Invalid JSON raises an `INVALID_JSON` validation error.
- An empty/whitespace string → `None`.

Useful for hidden inputs that round-trip structured data, or for form fields backing a `JSONField` model column. The rendered string value is the JSON-encoded form of the current dict.

### ListField

```python
f.ListField(
    type=None, *, strict=False, required=True, default=[],
    min_items=None, max_items=None, one_of=None, messages=None
)
```

For multiple values (e.g. `<select multiple>`, checkboxes). `type` is a callable to cast items (e.g. `int`). When `strict=False` (default), items that fail casting are silently skipped. When `strict=True`, a casting error raises an exception. An empty submission results in `[]`.

### DateField

```python
f.DateField(
    format='%Y-%m-%d', *, required=True, default=None,
    after_date=None, before_date=None, past_date=False, future_date=False,
    offset=0, one_of=None, messages=None
)
```

Converts to `datetime.date`. `offset` is timezone offset in hours for past/future checks. `after_date` and `before_date` accept either a `datetime.date` object or a date string.

### DateTimeField

```python
f.DateTimeField(
    format='%Y-%m-%dT%H:%M:%S', *, required=True, default=None,
    after_date=None, before_date=None, past_date=False, future_date=False,
    offset=0, one_of=None, messages=None
)
```

### TimeField

```python
f.TimeField(
    *, required=True, default=None,
    after_time=None, before_time=None, past_time=False, future_time=False,
    offset=0, one_of=None, messages=None
)
```

Unlike DateField and DateTimeField, TimeField has no `format` parameter — it parses time strings automatically.

### EmailField

```python
f.EmailField(
    *, required=True, default=None,
    check_dns=False, allow_smtputf8=False, strict=True, one_of=None, messages=None
)
```

Requires `email_validator` package. Normalizes the domain to lowercase with Unicode NFC normalization, and converts fullwidth/halfwidth characters.

| Option | Description |
|--------|-------------|
| `check_dns` | If `True`, makes DNS queries to verify the domain can receive mail |
| `allow_smtputf8` | Accept non-ASCII characters in the local part (before the @-sign). Requires SMTPUTF8 support along the mail route |
| `strict` | If `True`, validates that the local part is at most 64 characters long |

### URLField

```python
f.URLField(*, required=True, default=None, schemes=None, one_of=None, messages=None)
```

Default schemes: `["http", "https"]`. Normalizes the domain with UTS-46 (lowercasing, NFC normalization). Note that even if the format is valid, the URL is not guaranteed to be real — the purpose is to catch typing mistakes.

### SlugField

```python
f.SlugField(*, required=True, default=None, slugify=<default>, one_of=None, messages=None)
```

Auto-slugifies input. The default slugify function handles Latin-based characters but removes most non-Latin scripts (Cyrillic, Arabic, Hebrew, Hindi, etc.). Provide a custom `slugify` callable if you need broader Unicode support.

### FormField (Sub-form)

```python
f.FormField(FormClass, *, required=True, default=None)
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

### NestedForms (One-to-Many)

```python
f.NestedForms(FormClass, *, min_items=None, max_items=None, default=None, allow_delete=False)
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


## ORM Integration

Add a `Meta` class with `orm_cls`:

```python
class PageForm(f.Form):
    class Meta:
        orm_cls = Page

    title = f.TextField()
    content = f.TextField()
```

For Peewee (used by Proper), integration is automatic. `form.save()` either creates a new model instance (via `orm_cls.create(...)`) or updates the bound `object`, **and persists in either case** — no follow-up `object.save()` needed. Nested forms with `allow_delete=True` will call `object.delete()` for items marked with `_destroy`.

**Transactional by default**: when the form's `Meta.orm_cls` exposes a peewee-style database (`_meta.database.atomic()`), the field-save loop and the object save run inside a single transaction. If anything fails partway through — a side-effecting field save (e.g. an `AttachmentField` that uploads a file then INSERTs an attachment row), or the parent's INSERT/UPDATE itself — every preceding step rolls back. Consumers don't need to wrap controller actions in `with db.atomic():` for the simple form.save case; that wrapper is only useful when the action does *additional* DB work outside the form.

**Custom primary keys** for nested forms:

```python
class Meta:
    orm_cls = MyModel
    pk = "code"  # if PK field is not "id"
```


## Custom Error Messages

### Default Messages

Built-in error codes and their default messages:

| Error Code | Default Message |
|------------|-----------------|
| `required` | `"Field is required"` |
| `invalid` | `"Invalid value"` |
| `one_of` | `"Must be one of {one_of}"` |
| `gt` | `"Must be greater than {gt}"` |
| `gte` | `"Must be greater than or equal to {gte}"` |
| `lt` | `"Must be less than {lt}"` |
| `lte` | `"Must be less than or equal to {lte}"` |
| `multiple_of` | `"Must be a multiple of {multiple_of}"` |
| `min_items` | `"Must have at least {min_items} items"` |
| `max_items` | `"Must have at most {max_items} items"` |
| `min_length` | `"Must have at least {min_length} characters"` |
| `max_length` | `"Must have at most {max_length} characters"` |
| `pattern` | `"Invalid format"` |
| `past_date` | `"Must be a date in the past"` |
| `future_date` | `"Must be a date in the future"` |
| `after_date` | `"Must be after {after_date}"` |
| `before_date` | `"Must be before {before_date}"` |
| `after_time` | `"Must be after {after_time}"` |
| `before_time` | `"Must be before {before_time}"` |
| `past_time` | `"Must be a time in the past"` |
| `future_time` | `"Must be a time in the future"` |
| `invalid_url` | `"Doesn't seem to be a valid URL"` |
| `invalid_email` | `"Doesn't seem to be a valid email address"` |
| `invalid_slug` | `"A valid 'slug' can only have a-z letters, numbers, underscores, or hyphens"` |

Messages support `{placeholder}` substitution from `error_args`. Placeholders use the error code as the key name — for example, the message `"Must have at least {min_length} characters"` gets `{min_length}` replaced by the actual value.

### Global Messages (via base form)

```python
class BaseForm(f.Form):
    class Meta:
        messages = {
            "required": "This field cannot be empty",
            "custom_error": "Custom message here",
        }
```

Custom messages extend (not replace) the defaults. You can both override existing codes and add new ones in the same dictionary.

### Per-field Messages

```python
password = f.TextField(messages={"required": "Please enter your password"})
```

### Raising Custom Errors

```python
def validate_password(self, value):
    if "&" not in value:
        raise ValueError("must_contain", {"char": "&"})
    return value
```

First arg is the error code, second (optional) is `error_args` dict. The error args are available on the field as `field.error_args` and can be used in message placeholders:

```python
# messages = {"must_contain": "Must contain the character '{char}'."}
# field.error_args => {"char": "&"}
# field.error_message => "Must contain the character '&'."
```

### I18n Alternative

Use error codes directly in templates instead of messages:

```html+jinja
{% if field.error %}
  <div class="field-error">{{ _(field.error) }}</div>
{% endif %}
```
