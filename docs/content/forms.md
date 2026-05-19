---
title: Working with Forms
description: |
  Forms are how users send data into your application, and Formidable is the library Proper uses to define and validate them. This guide covers how to declare forms, validate input, save the results, and wire them into controllers.
number_headers: true
---

# Working with Forms

In this guide, you will learn how forms work and how they fit into the request cycle in your application.

- How to generate a form, and what the generator gives you.
- How `set_form`, `validate_form`, and `self.redo()` work together on `create` and `update`.
- How `form.save()` builds a model, persists it, and wraps the whole thing in a transaction.
- How to add custom validation, custom error messages, and pre-fill values.
- How to declare sub-forms and nested forms.

For the HTML side - render helpers, the wire format that comes back, and the markup patterns for nested forms and file uploads - see the [Rendering Forms guide](/docs/form_rendering).

---

## Introduction

A form has two jobs in a web application: it tells the user what data the application expects, and it tells the application what to do with what comes back. Proper hands both jobs to a small library called **Formidable**, which defines forms as Python classes and renders them as HTML.

A form is a regular Python class. You declare its fields, and the same object knows how to render itself, validate what came in, coerce strings into integers and dates, and hand the result back to your controller as a model instance or a dictionary.


:::note | Why forms are separate from models
A model describes a row in the database; a form describes a single submission. They have different concerns: a `Card` model has timestamps, foreign keys, and computed columns; a `CardForm` _only cares about the fields a user can edit_.

Keeping them separate also lets you have several forms for the same model (a public form, an admin form, a moderation form) without bending the model to fit each one.
:::

Once you're comfortable with the basics, check the [Formidable documentation](https://formidable.scaletti.dev/){target="_blank"} for the full field reference, every option, and every render helper.

---

## Generating a Form

Forms live in `myapp/forms/`, one class per file:

```
myapp/forms/
├── __init__.py
├── card.py
├── comment.py
└── session.py
```

Unlike controllers and models, forms are not registered anywhere. The controller imports the class directly:

```python
from ..forms.card import CardForm
```

You almost never write a form from scratch. The same generators that create controllers and models also create the matching form:

```bash
proper g resource Card title:str body:text
proper g controller Comment body:text
```

Both produce `myapp/forms/<name>.py`. For a resource, the form is connected to the model; for a plain controller, it isn't.

The generator turns each `field:type` pair from the command line into a Formidable field. The mapping is:

| Attr type            | Form field      |
| -------------------- | --------------- |
| `str`, `text`, `uuid` | `TextField`     |
| `int`, `bigint`      | `IntegerField`  |
| `float`, `decimal`   | `FloatField`    |
| `bool`               | `BooleanField`  |
| `date`               | `DateField`     |
| `datetime`           | `DateTimeField` |
| `time`               | `TimeField`     |

Anything outside that table (foreign keys, JSON columns, enums) is skipped at the form level - the form is a *suggestion*, and you adjust it once it exists.

Here's what `proper g resource Card title:str body:text` writes to `myapp/forms/card.py`:

```python
from proper import forms as f

from ..models import Card


class CardForm(f.Form):
    class Meta:
        orm_cls = Card

    title = f.TextField()
    body = f.TextField()
```

:::note
`proper.forms` re-exports everything from the Formidable library and adds Proper's own field types (like `AttachmentField`, covered in the [`AttachmentField`](#attachmentfield) section). A single `from proper import forms as f` covers everything you need; you don't import from `formidable` directly in a Proper application.
:::

We'll come back to `Meta.orm_cls` in [Saving the Form](#saving-the-form) - for now, just notice that it's there.

:::tip
The generator gives you a working form, not the *right* form. Open the file and adjust: mark optional fields with `required=False`, swap a `TextField` to `EmailField`, add length limits. The generator picks safe defaults; you tighten them.
:::

---

## Defining a Form

A form is a Python class that subclasses `f.Form`. Each field is a class attribute:

```python
from proper import forms as f


class TeamForm(f.Form):
    name = f.TextField()
    description = f.TextField(required=False)
```

Field names can be any valid Python identifier, with two restrictions:

- They cannot start with `_`.
- A handful of names are reserved: `is_valid`, `is_invalid`, `get_errors`, `hidden_tags`, `save`, `validate`, and `after_validate` (these are properties or methods on the form itself).

### The Field Types

Pick the field that matches the value you expect, not the field that matches the input element you'll render. A `TextField` can be rendered as a `<textarea>`, a `<select>`, or a list of radios; the field type controls validation and coercion, not appearance.

Field             | Use for                          | Common options
----------------- | -------------------------------- | ---------------------------------------------------------------
`f.TextField()`   | Short or long strings            | `min_length`, `max_length`, `pattern`, `one_of`
`f.EmailField()`  | Email addresses                  | `check_dns`
`f.URLField()`    | URLs                             | `schemes`
`f.SlugField()`   | URL slugs                        | auto-slugifies input
`f.IntegerField()`| Whole numbers                    | `gt`, `gte`, `lt`, `lte`, `multiple_of`
`f.FloatField()`  | Decimals                         | same as IntegerField
`f.BooleanField()`| Checkboxes                       | `required=False` by default
`f.DateField()`   | Dates                            | `after_date`, `before_date`, `past_date`, `future_date`
`f.DateTimeField()`| Dates with time                 | same as DateField
`f.TimeField()`   | Times                            | `after_time`, `before_time`
`f.FileField()`   | File uploads (validation only)   | -
`f.AttachmentField(A)` | File upload bound to a `ForeignKeyField(Attachment)` | `max_size`, `accept`, `service_name`; covered in [`AttachmentField`](#attachmentfield)
`f.ListField()`   | Multi-select, checkbox groups    | `type`, `min_items`, `max_items`
`f.FormField()`   | Embedded sub-form                | covered in [Sub-forms with `FormField`](#sub-forms-with-formfield)
`f.NestedForms()` | One-to-many sub-forms            | covered in [Nested Forms](#nested-forms)

Every field accepts the arguments `required=...` (`True` by the default for everything except `BooleanField`), `default=...` (a value or a callable evaluated at form instantiation), and `messages={...}` for per-field error strings.

For the full list of options on each field, see the [Formidable field reference](https://formidable.scaletti.dev/docs/fields/).

### Connecting a Form to a Model

Add a `Meta` class with `orm_cls` set to the model class:

```python
from proper import forms as f

from ..models import Page


class PageForm(f.Form):
    class Meta:
        orm_cls = Page

    title = f.TextField()
    content = f.TextField()
```

With `orm_cls` set, calling `form.save()` returns a `Page` instance built from the form data. Without it, `form.save()` returns a plain dictionary - which is what you want for forms with no model behind them (search forms, contact forms, settings panels). Both modes are covered in [Saving the Form](#saving-the-form).

### Form Inheritance

A form can subclass another form to add or replace fields:

```python
class BasePostForm(f.Form):
    title = f.TextField()
    content = f.TextField()


class ModeratorPostForm(BasePostForm):
    published_at = f.DateTimeField()
    layout = f.TextField(one_of=["post", "featured"])
```

A subclass field with the same name as a parent field overrides it.

:::warning
Deep inheritance makes forms hard to debug. Keep it to two levels (plus a base form) at most, and reach for composition - mixins, sub-forms, or shared validators - when you need more.
:::

---

## The Four Instantiation Patterns

A form is instantiated with up to two pieces of data:

```python
Form(reqdata=None, object=None, *, name_format="{name}", messages=None)
```

`reqdata` is the data the user submitted (a `MultiDict` from the request, or any dict-like object). `object` is the record the form is editing - a model instance, or a plain dictionary. Either, both, or neither can be present, which gives you four patterns:

```python
form = MyForm()                      # 1. blank
form = MyForm(reqdata)               # 2. submission only
form = MyForm({}, object)            # 3. pre-filled from object
form = MyForm(reqdata, object)       # 4. submission + object
```

Each one corresponds to one of the four form-bearing CRUD actions:

#### Empty form - for `new`

```python
form = CardForm()
print(form.title.value)   # None
```

The form has no values; it's only good for rendering the empty page. Validation will fail on any required field, but you wouldn't call `is_valid` here anyway.

#### Submission only - for `create`

```python
form = CardForm({"title": ["Hello"], "body": ["..."]})
print(form.title.value)   # "Hello"
```

The user just submitted the form; there's no existing record yet. If validation passes, `form.save()` creates a new model instance.

#### Object only - for `edit`

```python
form = CardForm({}, card)
print(form.title.value)   # the existing card's title
```

The form is pre-filled from the record so the user can see and modify it. No submission has happened yet.

#### Submission and object - for `update`

```python
form = CardForm(reqdata, card)
```

The user submitted changes to an existing record. Submission values take precedence over object values, so the form shows what the user typed, not what was stored.

The generator's `set_form` callback handles all four cases with a single line of code (covered in [The Controller Side](#the-controller-side)) - you almost never write these by hand.

---

## The Controller Side

A generated resource controller wires three callbacks into the request cycle:

```python
@router.resource("cards")
class CardController(AppController):
    before = [
        {"do": "set_card", "exclude": ["index", "new", "create"]},
        {"do": "set_form", "exclude": ["index", "show", "delete"]},
        {"do": "validate_form", "only": ["create", "update"]},
    ]
```

The round-trip looks like this:

```
GET /cards/new -→ empty form -→ render new.jx

POST /cards -→ form.validate
                  │
                  ├─ valid   -→ save and redirect to show.jx
                  └─ invalid -→ re-render new.jx with errors at 422
```

`set_card` loads the record (covered in the [Controllers guide](/docs/controllers)). The other two are about the form. Together they handle all four instantiation patterns from [The Four Instantiation Patterns](#the-four-instantiation-patterns):

| Action  | `set_card` runs? | `set_form` builds                       | Pattern |
| ------- | ---------------- | --------------------------------------- | ------- |
| `new`   | no               | `CardForm({}, object=None)`             | 1       |
| `create`| no               | `CardForm(self.params, object=None)`    | 2       |
| `edit`  | yes              | `CardForm({}, object=self.card)`        | 3       |
| `update`| yes              | `CardForm(self.params, object=self.card)` | 4     |

### `set_form`

The generator writes this method at the bottom of the controller:

```python
def set_form(self):
    obj = getattr(self, "card", None)
    self.form = CardForm(self.params, object=obj)
```

That's the entire build step. `getattr(self, "card", None)` returns the loaded record on `edit`/`update` and `None` on `new`/`create`. `self.params` carries the submission on `create`/`update` and is empty on `new`/`edit`. The form sorts out the rest.

For `edit`, request data is empty and the form is pre-filled from the record. For `update`, request values take precedence over object values, so the form shows what the user just typed (with the rest of the record's fields filling the gaps).

### `validate_form` and `self.redo()`

`validate_form` lives in the `FormValidation` concern at `myapp/controllers/concerns/form_validation.py`:

```python
class FormValidation(Concern):
    def validate_form(self):
        form = getattr(self, "form", None)
        if form and form.is_invalid:
            self.redo()
```

When the form is invalid, the concern calls `self.redo()`. This is the one Proper-specific helper worth understanding:

`self.redo()` is a controller method that re-renders the matching form template with a `422 Unprocessable Entity` status - `new.jx` for a failed `create`, `edit.jx` for a failed `update`. The `FormValidation` concern calls it for you when a form is invalid; you'll rarely call it yourself, but it's there if you need to reject a submission from inside an action.

Once `validate_form` halts the request, the action body never runs. Your `create` and `update` methods only execute on valid submissions.

### The Action Bodies

With the callbacks doing the setup, the action bodies are tiny:

```python
def new(self):
    pass        # set_form built an empty CardForm; the template renders it

def create(self):
    card = self.form.save()
    self.response.redirect_to("Card.show", card, flash="Card was created")

def edit(self):
    pass        # set_form pre-filled from self.card; the template renders it

def update(self):
    card = self.form.save()
    self.response.redirect_to("Card.show", card, flash="Card was updated")
```

`new` and `edit` do nothing - they just render their templates with the form the callback built. `create` and `update` look identical, even though one is creating and the other is updating - the form knows which case it's in because `set_form` already gave it the right `object` argument. The next section walks through what `form.save()` actually does.

---

## Saving the Form

`form.save()` does three things in one call: it collects the validated field values, applies them to a Python object, and persists that object through the ORM. The whole thing runs inside a single transaction.

For a `create`, that's an INSERT. For an `update`, it's an UPDATE. For a form with no `orm_cls`, it's neither - you get a plain dict back. You write one line and pick what to do with the result.

### The Three Return Shapes

The form constructor takes up to two arguments (`reqdata`, `object`); together with whether the form has `Meta.orm_cls`, that gives three useful combinations:

| `Meta.orm_cls`? | Built with `object`? | `form.save()` returns |
| --------------- | -------------------- | --------------------- |
| no              | no                   | a plain dict (no persistence) |
| no              | yes (dict or model)  | the same object, updated (no persistence) |
| yes             | no                   | a new model instance, INSERTed |
| yes             | yes (a model)        | the same model, UPDATEd |

The first two rows are for forms with no model behind them (search forms, contact forms) - covered in [Forms Without a Model](#forms-without-a-model). The bottom two are the model-backed flow, and in both cases the row is on disk by the time `save()` returns.

### Transactions

For ORM-bound forms, the whole save - every field's `save()` plus the parent INSERT/UPDATE - runs inside a single transaction.

If `Meta.orm_cls` exposes `_meta.database.atomic()` (Peewee's pattern), the form opens an `atomic()` block. When nested inside an outer atomic block, that becomes a savepoint. Any exception raised during the field-save loop or the parent save propagates up and rolls everything back.

This matters most for fields with side effects - an [`AttachmentField`](#attachmentfield) that uploads a file and INSERTs a child row, a custom field that hits an external service. If the parent INSERT fails, you don't end up with an orphan attachment row pointing at a freshly-uploaded file.

### Adding Fields That Aren't on the Form

`form.save()` accepts keyword arguments that get merged into the data before the row is written:

```python
def create(self):
    photo = self.form.save(user_id=current.user.id)
```

Use this for values that come from the server, not the user input: the current tenant or user's id, a timestamp you control, etc. You don't want these on the form (a malicious user could send their own value), and you don't want them in `set_form` (the form would then receive an unexpected key). `**extra` is the right place.

### Calling `save()` on an Invalid Form

`form.save()` raises `ValueError` if you call it before validation passes. The `validate_form` callback handles that for you on `create` and `update` - if the form is invalid, the action body never runs, and you never reach the `save()` call.

If you skip the callback (custom flow, JSON API), call `form.is_valid` first.

---

## Validation

Field validation runs in this order:

1. **Custom filters** - your `filter_<fieldname>` method, if defined.
2. **Built-in validators** - the constraints declared on the field (`required`, `min_length`, `gt`, `one_of`, `pattern`, ...).
3. **Custom validator** - your `validate_<fieldname>` method, if defined.
4. **Form-wide validation** - the `after_validate` method, if defined.

![Filter flow](/assets/images/forms/filter-flow-l.svg){height=100 .center .only-light}
![Filter flow](/assets/images/forms/filter-flow-d.svg){height=100 .center .only-dark}

![Validate flow](/assets/images/forms/validate-flow-l.svg){height=70 .center .only-light}
![Validate flow](/assets/images/forms/validate-flow-d.svg){height=70 .center .only-dark}

### Custom Filters

A filter transforms the value before validation. Add a method named `filter_<fieldname>`:

```python
class UserForm(f.Form):
    email = f.EmailField()

    def filter_email(self, value):
        if value is None:
            return value
        return value.lower().strip()
```

Always check for `None` first - filters receive `None` when the field has no input.

:::warning | `filter_` for FormField and NestedForms are different
For sub-forms (`FormField`) and nested forms (`NestedForms`), the filter signature is `(reqvalue, objvalue)` and it must return a `(reqvalue, objvalue)` tuple. The split lets you transform request data and object data separately - useful, for example, for clearing a sub-form when a parent flag is set.
:::

### Prefer Built-in Constraints

Most validation is more readable as a field option than as a custom method:

```python
from proper import forms as f

class ProductForm(f.Form):
    name = f.TextField(min_length=3, max_length=80)
    sku = f.TextField(pattern=r"^[A-Z]{3}-\d{4}$")
    quantity = f.IntegerField(gte=0, lte=10_000)
    category = f.TextField(one_of=["book", "music", "movie"])
```

Built-in constraints come with default error messages, work with localization, and read cleanly. Reach for a custom validator only when no built-in fits.

### Custom Validators

Add a method named `validate_<fieldname>` to the form. It receives the field's value, can raise `ValueError("error_code")` to fail validation, and must return the value (transformed or not):

```python
class CommentForm(f.Form):
    body = f.TextField()

    def validate_body(self, value):
        if "spam" in (value or "").lower():
            raise ValueError("looks_like_spam")
        return value
```

The first argument to `ValueError` is the *error code*, not the human-readable message. The message lookup happens in the messages dict (covered in [Error Messages](#error-messages)). This split is what makes localization possible.

You can also pass a dict as the second argument, which becomes `field.error_args` and lets you fill placeholders in the message:

```python
def validate_body(self, value):
    if len(value) > 1000:
        raise ValueError("too_long", {"max": 1000})
    return value

# messages = {"too_long": "Body cannot exceed {max} characters"}
```

### Form-Level Validation

Some checks involve more than one field. Override `after_validate` to run them. It receives no arguments and must return `True` if the form is valid:

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

To indicate which field failed, set `field.error` directly on the offending field. If you don't, the user sees a form-level failure with no hint about what to fix.

`after_validate` only runs if every individual field passed - if the password fields are required and one was empty, `after_validate` is skipped (the user sees the "required" error first).

### Triggering Validation

You don't usually call `form.validate()` directly. Two properties do it for you and cache the result:

```python
form.is_valid     # True / False, runs validation on first access
form.is_invalid   # not is_valid
```

The result is cached, so repeated reads don't re-validate. If you need to re-validate after changing values manually, call `form.validate()` again.

---

## Error Messages

When a field fails validation, three pieces of state are set:

- `field.error` - the *error code*, a short string like `"required"` or `"min_length"`.
- `field.error_args` - an optional dict with extra context for the message (`{"min_length": 10}`).
- `field.error_message` - the human-readable string, looked up from the messages dict using the error code.

`field.error_tag()` renders the message as `<div class="field-error">...</div>`. You only see the message; the code is what you customize.

### The Default Messages

Formidable ships with default messages for every built-in error code:

Code              | Default message
----------------- | -----------------------------------------
`required`        | Field is required
`invalid`         | Invalid value
`one_of`          | Must be one of {one_of}
`min_length`      | Must have at least {min_length} characters
`max_length`      | Must have at most {max_length} characters
`gt`              | Must be greater than {gt}
`gte`             | Must be greater than or equal to {gte}
`lt`              | Must be less than {lt}
`lte`             | Must be less than or equal to {lte}
`pattern`         | Invalid format
`invalid_email`   | Doesn't seem to be a valid email address
`invalid_url`     | Doesn't seem to be a valid URL
`invalid_slug`    | A valid 'slug' can only have a-z letters, numbers, underscores, or hyphens
`past_date`       | Must be a date in the past
`future_date`     | Must be a date in the future
`file_too_large`  | File size should be {max_size} or less
`invalid_content_type` | Invalid content type

Placeholders like `{one_of}` and `{min_length}` are filled from `field.error_args` - the same key as the error code itself.

### Three Levels of Customization

You can override messages in three places, from most specific to least:

**Per-field**, with the `messages` keyword on the field:

```python
class LoginForm(f.Form):
    password = f.TextField(messages={"required": "Please enter your password"})
```

**Per-form**, with `Meta.messages`:

```python
class LoginForm(f.Form):
    class Meta:
        messages = {
            "required": "This field is mandatory",
            "invalid_email": "That email looks wrong",
        }

    email = f.EmailField()
    password = f.TextField()
```

**App-wide**, by inheriting from a base form:

```python
class AppForm(f.Form):
    class Meta:
        messages = {
            "required": "This field is mandatory",
        }


class LoginForm(AppForm):
    email = f.EmailField()
    password = f.TextField()
```

Custom messages *extend* the defaults rather than replace them. A field with a per-field message uses that one; otherwise it falls back to the form's, then the parent form's, then the default.

### Custom Error Codes

Custom validators raise `ValueError` with whatever code you choose:

```python
class NewPasswordForm(f.Form):
    password = f.TextField(
        messages={"must_contain": "Must contain a '{char}' character"},
    )

    def validate_password(self, value):
        if "&" not in value:
            raise ValueError("must_contain", {"char": "&"})
        return value
```

The code (`"must_contain"`) and the args (`{"char": "&"}`) flow through to `field.error`, `field.error_args`, and the message lookup.

### Translating Error Messages

Two approaches work, depending on whether your locale catalog is keyed by error code or by message:

**By message, via the messages dict.** Pass a localized dict at form instantiation:

```python
form = MyForm(self.params, object=card, messages=MESSAGES[current.locale])
```

**By code, in the template.** Skip the messages dict and translate the error code directly:

```html+jinja
{% if field.error %}
  <span class="field-error">{{ _(field.error) }}</span>
{% endif %}
```

The second approach is what the [Internationalization guide](/docs/i18n) recommends - it puts every translatable string in one catalog, alongside the rest of your UI.

---

## Forms Without a Model

Not every form is connected to a database table. A search form, a contact form, a settings panel, a "send invitation" form - any form whose result you act on but don't store as a row.

Drop the `Meta` class entirely:

```python
from proper import forms as f


class ContactForm(f.Form):
    name = f.TextField()
    email = f.EmailField()
    message = f.TextField(min_length=10, max_length=2000)
```

Now `form.save()` returns a plain dict instead of a model instance:

```python
@router.resource("contact", pk=None)
class ContactController(AppController):
    before = [
        {"do": "set_form",      "exclude": ["index", "show"]},
        {"do": "validate_form", "only": ["create"]},
    ]

    def show(self):
        pass

    def create(self):
        data = self.form.save()
        SupportMailer.contact_received(data).deliver_later()
        self.response.redirect_to("Contact.show", flash="Thanks - we'll be in touch.")

    # Private

    def set_form(self):
        self.form = ContactForm(self.params)
```

`set_form`, `validate_form`, `self.redo()` - all the same callbacks as before, all the same templates (`new.jx`, `edit.jx`). The only thing that changes is what comes out of `form.save()` and what you do with it.

This is also the right shape for forms that produce a JSON request body for an external service, build a search query, or update a session preference - anywhere you'd otherwise be parsing `self.params` by hand.

---

## Sub-forms with `FormField`

When a form has a one-to-one relationship with another form - a profile that has settings, a page that has metadata, a user that has a single billing address - use `f.FormField`.

### Defining a Sub-form

The sub-form is a regular form class. The parent form embeds it with `f.FormField`:

```python
from proper import forms as f


class SettingsForm(f.Form):
    locale = f.TextField(default="en_us")
    timezone = f.TextField(default="utc")


class ProfileForm(f.Form):
    name = f.TextField()
    settings = f.FormField(SettingsForm)
```

For the markup to render this in HTML, see [Rendering Forms - Sub-forms](/docs/form_rendering#sub-forms-with-formfield).

### What `save()` Returns

The sub-form's `Meta.orm_cls` controls what the parent's `save()` returns:

- **With `orm_cls`**: the sub-form's value is an ORM object, useful for one-to-one foreign keys.
- **Without `orm_cls`**: the sub-form's value is a plain dict, useful for JSON columns.

The dict variant is the more common one. Storing settings as a JSON column on the parent table avoids a join and a second migration:

```python
# models/profile.py
class Profile(BaseModel):
    name = TextField()
    settings = JSONField(default=dict)


# forms/profile.py
class SettingsForm(f.Form):  # no Meta, no orm_cls
    locale = f.TextField(default="en_us")
    timezone = f.TextField(default="utc")


class ProfileForm(f.Form):
    class Meta:
        orm_cls = Profile

    name = f.TextField()
    settings = f.FormField(SettingsForm)
```

`form.save()` returns a `Profile` instance whose `settings` field is a dict like `{"locale": "...", "timezone": "..."}`. The Peewee `JSONField` handles the serialization.

---

## Nested Forms

When a form has a one-to-*many* relationship - a person with several addresses, a recipe with several ingredients, a poll with several options - use `f.NestedForms`. Users can add and remove sub-forms in the browser, and Formidable tracks creates, updates, and deletions for you.

### Defining a Nested Form

The example for the rest of this section is a `Person` with many `Address` records:

```python
from proper import forms as f

from ..models import Address, Person


class AddressForm(f.Form):
    class Meta:
        orm_cls = Address

    kind = f.TextField()
    street = f.TextField()


class PersonForm(f.Form):
    class Meta:
        orm_cls = Person

    name = f.TextField()
    addresses = f.NestedForms(AddressForm)
```

For the markup to render the sub-forms in HTML - including the dynamic add/remove JavaScript - see [Rendering Forms - Nested Forms](/docs/form_rendering#nested-forms).

### Allowing Deletions

By default, `NestedForms` doesn't let users delete sub-forms - only add and edit. To allow deletion, pass `allow_delete=True`:

```python
class PersonForm(f.Form):
    class Meta:
        orm_cls = Person

    name = f.TextField()
    addresses = f.NestedForms(AddressForm, allow_delete=True)
```

With deletion enabled, the rendered HTML includes a hidden `_destroy` input on each sub-form. When that input has a non-empty value at submit time, `form.save()` calls `delete()` on the matching ORM object. The Rendering Forms guide shows [how the JavaScript fills `_destroy`](/docs/form_rendering#dynamic) when the user clicks a remove button.

### Custom Primary Keys

`NestedForms` uses primary keys to track which sub-form maps to which existing record. If the model's primary key isn't named `id`, declare the right name in the sub-form's `Meta`:

```python
class IngredientForm(f.Form):
    class Meta:
        orm_cls = Ingredient
        pk = "code"

    name = f.TextField()
    quantity = f.FloatField()
```

### What `save()` Returns

The same rule as `FormField`:

- **With `orm_cls` on the sub-form**: the nested value is a list of ORM objects.
- **Without `orm_cls`**: the nested value is a list of dicts.

For the `Person`/`Address` example, `form.save()` returns a `Person` instance whose `addresses` field holds a list of `Address` instances - new ones for sub-forms the user just added, existing ones whose primary keys matched records the form was instantiated with.

---

## `AttachmentField`

`f.FileField` only validates that *something* was uploaded - the controller still has to read the upload, build an `Attachment`, save it to storage, and assign the FK on the model. Proper adds a second field, `f.AttachmentField`, that does all of that work for you. It's the recommended path whenever a model has a `ForeignKeyField(Attachment)` column.

### Declaring an `AttachmentField`

The field takes the `Attachment` class as its first positional argument, plus the same `required`, `default`, and `messages` keyword arguments as any other field, two storage-specific options, and two upload validators:

```python
from proper import forms as f

from ..models import Attachment, Book


class BookForm(f.Form):
    class Meta:
        orm_cls = Book

    title = f.TextField()
    cover = f.AttachmentField(Attachment, required=False)
```

The options are the usual `required`, `default`, and `messages`, plus:

- **`service_name`** - which storage service to upload through (matches a key in your `STORAGE` config). Defaults to the default service.
- **`max_size`** - reject uploads larger than this many bytes. Covered in [Validating Uploads](#validating-uploads).
- **`accept`** - a list of allowed content-type glob patterns (e.g. `["image/*"]`). Covered in [Validating Uploads](#validating-uploads).

The matching column on the model is a nullable foreign key:

```python
class Book(BaseModel):
    title = pw.CharField()
    cover = pw.ForeignKeyField(Attachment, null=True)
```

### Why `AttachmentField` Is Different

Every other field on a form is a *value translator* - it takes a string (or a few strings) from the request, validates and coerces them, and hands the result back through `form.save()`. `AttachmentField` does more: when the user uploads a new file, the field's `save()` step uploads the file through the storage service, INSERTs an `Attachment` row, purges the previous attachment (if any), and returns the new `Attachment` for the FK.

Because [the whole save runs in a transaction](#transactions), an upload + INSERT either both succeed or both roll back together. The `purge_later()` call on a replaced original runs after the transaction commits, so the bytes for the old file survive until the new save is durable.

### The Three Behaviors

The field interprets the incoming request in three ways depending on what the browser sent:

User did              | `<field>[file]` | `<field>[_destroy]` | Action on `save()`
--------------------- | --------------- | ------------------- | -------------------------------------------
Uploaded a new file   | populated       | (any)               | save new attachment, purge the previous one
Clicked "Remove"      | empty           | `"1"`               | clear the FK, purge the previous attachment
Left the field alone  | empty           | `"0"` or absent     | preserve the existing attachment

The two HTML inputs that drive this (`<field>[file]` and `<field>[_destroy]`) are produced by the field's render helpers, covered in [Rendering Forms - Attachment uploads](/docs/form_rendering#attachment-uploads).

### Validating Uploads

Two optional keyword arguments add server-side validation to an `AttachmentField`. They run during `form.validate()`, before the upload would otherwise be saved, and produce normal field errors that render through `error_tag()` like any other validation failure.

```python
class BookForm(f.Form):
    class Meta:
        orm_cls = Book

    cover = f.AttachmentField(
        Attachment,
        max_size=5 * 1024 * 1024, # 5 MB
        accept=["image/*"],       # any image type
        service_name="public",
        required=False,
    )
```

**`max_size`** rejects uploads whose `size` (in bytes) exceeds the limit. The boundary is inclusive - an upload of exactly `max_size` bytes passes. The error code is `errors.FILE_TOO_LARGE`, with `error_args={"max_size": "<formatted size>"}` rendered through `format_size` so the message reads `"File size should be 5 MB or less"` instead of `"5242880"`.

**`accept`** rejects uploads whose `content_type` doesn't match any of the listed patterns. Matching is via [`fnmatch`](https://docs.python.org/3/library/fnmatch.html), so `*` is a wildcard:

- `"image/*"` matches `image/png`, `image/jpeg`, `image/gif`, etc.
- `"application/pdf"` is a literal pattern - it matches `application/pdf` exactly.
- `"*/*"` matches any content type that has the standard `type/subtype` shape.

Patterns and the upload's content type are both lowercased before matching, so `"IMAGE/PNG"` against `"image/*"` still matches.

Pass several patterns to allow several kinds of files:

```python
attachment = f.AttachmentField(
    Attachment,
    accept=["image/*", "application/pdf", "video/mp4"],
)
```

The error code is `errors.INVALID_CONTENT_TYPE`, with `error_args={"accept": [...]}`.

:::tip | Same patterns as the HTML `accept` attribute
The Python `accept` argument and the HTML `<input type="file" accept="...">` attribute use the same syntax for content-type patterns. Setting both to `"image/*"` keeps the file-picker filter and the server-side validator in sync: the browser's picker hides non-images, and the server rejects them anyway if the user uploads one through DevTools or a non-browser client.
:::

:::note | Soft limit, not the hard ceiling
`max_size` is a per-field, application-level limit. It runs after the request parser has already accepted the upload, so it's the right place for "covers should be ≤ 5 MB" but not for "stop runaway uploads that would exhaust the server." The framework's hard ceiling is the `MAX_FORM_PART_SIZE` setting in `config/main.py`, which is enforced by the parser before any field even sees the data.
:::

Both checks are skipped when the underlying value doesn't carry the relevant attribute. That matters for forms bound to an existing record - the bound `Attachment` is a database row, not a fresh upload, and shouldn't be re-validated against current rules. The user pressing "Submit" without touching the file input lets the existing attachment through unchanged.

`accept=None` or `accept=[]` disables the content-type check entirely; same for `max_size=None`.

When both rules are configured and an upload fails both, `max_size` is checked first, so the size error is the one shown.

### When to Use `FileField` Instead

Reach for `FileField` when:

- The upload isn't tied to an `Attachment` foreign key (a one-off CSV import, a parser that reads bytes and discards the file, an attachment that needs a non-standard storage flow).
- You need full control over the upload pipeline (e.g.: custom validation against the bytes, custom filename rules, etc.) and the controller is the right place to do it.

For the typical "user uploads an avatar / a cover image / a profile photo" case, `AttachmentField` is the simpler choice.

---

## CSRF and Form Submissions

Proper protects state-changing requests against CSRF using the `OriginProtection` concern, which is mixed into `AppController` by default. It checks the browser's `Sec-Fetch-Site` and `Origin` headers and rejects cross-origin POSTs - no token in the form, no special template tag.

That's why the generated `form.jx` doesn't include a `<input name="_csrf_token">`. You don't need one for browser submissions.

---

## Testing Forms

There are two natural ways to test a form: as a unit, in isolation from the controller; or as a piece of the request cycle, through the controller.

### Unit-Testing a Form

Forms are plain classes. You can build one with a dict and assert on the field values without hitting `save()`:

```python
def test_card_form_requires_title():
    form = CardForm({"body": ["Lorem ipsum"]})
    assert form.is_invalid
    assert form.title.error == "required"

def test_card_form_filters_and_coerces():
    form = CardForm({"title": ["  Hi  "], "body": ["..."]})
    assert form.is_valid
    assert form.title.value == "Hi"   # whitespace stripped
```

Wrap each value in a list - that's the shape Formidable expects, since it mirrors a real `MultiDict` where every key can have multiple values.

Avoid calling `form.save()` in pure unit tests: when the form has an `orm_cls`, `save()` INSERTs (or UPDATEs) through the ORM, so you need a database or a fake. For that, write an integration test against the controller (next subsection) and let the test database handle the round-trip.

### Integration-Testing Through the Controller

For end-to-end tests, use Proper's `TestClient` and assert on the response:

```python
def test_create_card_with_invalid_data(client):
    response = client.post("/cards", form={"body": "..."})  # missing title
    assert response.status == 422
    assert "field-error" in response.text
```

The `422` status is what `self.redo()` returns. It's the easiest way to assert "the form was rejected" without coupling your test to the exact error message.

The [Testing guide](/docs/testing) covers `TestClient` in depth, including signing in users, uploading files, and following redirects.

---

## What's Next

Forms are connected to almost every other piece of a Proper application. Once you're comfortable with the basics, these guides take you further:

- [Rendering Forms](/docs/form_rendering) - the HTML side: render helpers, manual markup, the wire format that comes back, sub-form and nested-form rendering, file uploads, and the method override trick.
- [Formidable documentation](https://formidable.scaletti.dev/) - the full field reference, every option, every render helper.
- [File Storage](/docs/storage) - the `Attachment` model behind `AttachmentField`, image variants, content-type validation, and serving private files through signed URLs.
- [Internationalization (i18n)](/docs/i18n) - translating error messages, formatting dates and numbers per locale.
