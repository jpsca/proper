---
title: Formidable Forms
description: Form validation library — defining forms, constructor, validation and saving, field attributes and rendering, ORM integration, error messages
last_verified: 2026-11-01
sources:
  - src/proper/forms
  - src/proper/concerns/form_validation.py
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

Field names must be valid Python identifiers (an attribute whose name starts with `_` is ignored, not treated as a field) and cannot be named `get_errors`, `hidden_tags`, `save`, `validate`, or `after_validate` (these are reserved). Fields named `is_valid` or `is_invalid` are also rejected if defined as `Field` instances.

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

Request data values take precedence over object data. When no data is provided (pattern 1), fields hold their `default` (usually `None`) and `is_valid` is `True`: the required checks run only when request data is set. Such a form exists to be rendered, not validated.

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
form.get_errors()   # Returns dict of {field_name: error_code} for all fields with errors.
                    # For a FormField the value is the sub-form's own error dict; for NestedForms
                    # it is "invalid" and field.error_args maps each sub-form index to its errors.
                    # For a FormField the value is the sub-form's own error dict; for NestedForms
                    # it is "invalid" and field.error_args maps each sub-form index to its errors
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
| `f.RichTextField()` | Rich text body bound to a model `RichTextField` | `required=False`; `strip` fixed to `False` |
| `f.JSONField()` | JSON text parsed to a dict | — |

Every field also takes `label=` (the text `label()` renders when called without one) and `messages=`; Proper's `JSONField` and `AttachmentField` don't take `label`.
| `f.RichTextField()` | Rich text body bound to a model `RichTextField` | `required=False`; `strip` fixed to `False` |
| `f.JSONField()` | JSON text parsed to a dict | — |

Every field also takes `label=` (the text `label()` renders when called without one) and `messages=`; Proper's `JSONField` and `AttachmentField` don't take `label`.

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

Always check for `None` before operating on the value — filters receive the field's default (`None` unless `default=` is set) when the field has no input.

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
| `field.error` | Error code string (a dict for `FormField`) or `None` |
| `field.error_args` | Optional dict of extra error details for message placeholders |
| `field.error_message` | Human-readable error from messages dict |

### Render Methods

All render methods accept `**attrs` for additional HTML attributes. Use trailing underscore for Python reserved words: `class_="text-sm"` renders as `class="text-sm"`.

Fields with the `required` option automatically add the `required` HTML attribute (except `checkbox()`, `radio()` and `hidden_input()`). Fields with errors automatically add `aria-invalid="true"` and `aria-errormessage` attributes.

| Method | Renders | Notes |
|--------|---------|-------|
| `field.label(text=None, **attrs)` | `<label>` element | If `text` is `None`, uses the field's `label=` argument, else the field name with underscores as spaces, capitalized |
| `field.error_tag(**attrs)` | `<div class="field-error">` | Only rendered if error exists. Custom `class_` replaces default |
| `field.text_input(**attrs)` | `<input type="text">` | |
| `field.textarea(**attrs)` | `<textarea>` | |
| `field.select(options, **attrs)` | `<select>` | Options as `[(value, text), ...]`. Matching values get `selected`. Automatically adds `multiple` for ListField |
| `field.checkbox(**attrs)` | `<input type="checkbox">` | Checked when field value is truthy. For a `BooleanField` it also renders `<input type="hidden" name="..." value="0">` before the checkbox so unchecking is submitted (skipped when `disabled`); add it yourself in manual HTML |
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

The table above is enough to pick a field. Every option of every field, with examples (`AttachmentField`, `RichTextField`, `FormField`, `NestedForms` included), is in [reference/form_fields.md](reference/form_fields.md).


## ORM Integration

Add a `Meta` class with `orm_cls`:

```python
class PageForm(f.Form):
    class Meta:
        orm_cls = Page

    title = f.TextField()
    content = f.TextField()
```

For Peewee (used by Proper), integration is automatic. `form.save()` either creates a new model instance (via `orm_cls.create(...)`) or updates the bound `object`, **and persists in either case** — no follow-up `object.save()` needed. Nested forms with `allow_delete=True` will call `object.delete_instance()` (Peewee) or `object.delete()` for items marked with `_destroy`.

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
| `invalid_json` | `"Invalid JSON format"` |
| `file_too_large` | `"File size should be {max_size} or less"` |
| `invalid_content_type` | `"Invalid content type"` |
| `invalid_json` | `"Invalid JSON format"` |
| `file_too_large` | `"File size should be {max_size} or less"` |
| `invalid_content_type` | `"Invalid content type"` |

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
