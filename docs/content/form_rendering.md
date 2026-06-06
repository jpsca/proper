---
title: Rendering Forms
description: |
  The HTML side of forms in Proper: how to render fields with the built-in helpers, how to write the markup yourself, the wire format that comes back, and the rendering patterns for sub-forms, nested forms, file uploads, and method override.
number_headers: true
---

# Rendering Forms

In this guide, you will learn how a form turns into HTML, how the data that comes back is shaped, and the rendering patterns Proper expects you to use.

- How the `<Form>` Jx component wraps your inputs and handles requests beyond `GET` and `POST`.
- How the field render helpers (`label`, `text_input`, `error_tag`, ...) produce HTML.
- How to write form markup by hand when the helpers don't fit.
- How to render sub-forms and nested forms, including dynamic add and remove with JavaScript.
- How to render file upload forms and forms that submit to other servers.

This guide is the companion to [Working with Forms](/docs/forms), which covers the controller flow, validation, and saving. If you haven't read that one yet, the introduction to this guide will still make sense, but the controller-side code samples will not.

---

## Introduction

A form has two halves. The first half - declaring fields, validating input, and saving the result - is covered in [Working with Forms](/docs/forms). The second half is the HTML the user sees, the data that comes back when they submit, and the markup patterns for everything from a basic text input to a dynamic list of nested sub-forms. That second half is what this guide is about.

Proper's rendering story has three pieces:

- **A framework component**, `<Form>`, that emits the `<form>` tag with the right `action`, `method`, `enctype`, and method-override input.
- **Field render helpers** like `field.label()` and `field.text_input()` that produce labels, inputs, and error tags from the form object.
- **A naming convention** for HTML inputs - bracketed paths like `user[name]` or `addresses[0][street]` - that turns flat form submissions into nested Python data on the way back in.

---

## The `<Form>` Component

Every form your application renders goes through the framework `<Form>` component, defined in `views/form.jx`. It's a small Jx component that takes care of three things:

- Emits the `<form>` HTML tag with the right `method`, `action`, and (optionally) `enctype` attributes.
- Adds a hidden `_method` input when you ask for `PATCH`, `PUT`, or `DELETE` (covered in [Method Override (PATCH, PUT, DELETE)](#method-override-patch-put-delete)).
- Sets `novalidate` by default, so browser-side validation gets out of the way of Proper's server-side validation.

You import it the same way you'd import any Jx component:

```html+jinja
{#import "form.jx" as Form #}
```

And then use it as a tag:

```html+jinja
<Form action={{ url_for('Card.create') }}>
  <input name="title" required>
  <button type="submit">Create</button>
</Form>
```

That produces:

```html
<form method="post" action="/cards" novalidate>
  <input name="title" required>
  <button type="submit">Create</button>
</form>
```

### The Props

The `<Form>` component takes four arguments, all optional:

Prop          | Default | What it does
------------- | ------- | ------------------------------------------------------------------
`action`      | `""`    | The URL the form posts to. Always pass this, in practice.
`method`      | `"post"`| `"get"`, `"post"`, or one of `"patch"` / `"put"` / `"delete"` / `"query"`.
`multipart`   | `False` | When `True`, sets `enctype="multipart/form-data"` for file uploads.
`novalidate`  | `True`  | Tells the browser to skip its own form validation.

`action` is the URL string. Use `url_for` to generate it:

```html+jinja
<Form action={{ url_for('Card.create') }}>
```

`method` is lowercase. Anything other than `"get"` or `"post"` triggers method override (next section).

`multipart` switches the encoding so file uploads work. Forget this and `<input type="file">` will still appear in the page, but the file bytes won't be sent.

`novalidate` defaults to `True` because Proper's validation is what should win. If you want browser-side validation back, pass `novalidate=False`.

### What `<Form>` Doesn't Do

A few things you might expect, that the `<Form>` component does *not* handle:

- **CSRF tokens.** Proper protects against cross-site request forgery via the `OriginProtection` concern, which checks the browser's `Sec-Fetch-Site` and `Origin` headers. There's no `<input name="_csrf_token">` to add. See [CSRF and Form Submissions](/docs/forms#csrf-and-form-submissions) in the Working with Forms guide for the details.
- **Field rendering.** `<Form>` is just the wrapper. Inside it, you place field markup either with the render helpers (next section) or by hand.
- **Submit buttons.** You write your own. Convention is `<button type="submit">Create card</button>` or similar at the bottom of the form.

---

## Method Override (PATCH, PUT, DELETE)

HTML forms only support two methods: `GET` and `POST`. The browser will not honor `<form method="patch">` or `<form method="delete">`. This is a limitation of the HTML form spec, not of any framework.

To work around it, Proper uses a convention shared with Rails, Sinatra, and most other server-side frameworks: the form is `POST`-ed with a hidden `_method` input that names the *real* HTTP method. The request layer then rewrites the request's method before the router sees it.

### What You Write

In your template, write the method you want:

```html+jinja
<Form method="patch" action={{ url_for('Card.update', card) }}>
  ...
</Form>
```

Or for a delete:

```html+jinja
<Form method="delete" action={{ url_for('Card.delete', card) }}>
  <button type="submit">Delete</button>
</Form>
```

### What the Browser Sends

The `<Form>` component rewrites your `method` to `post` and adds a hidden input. The HTML it produces for `<Form method="patch">` is:

```html
<form method="post" action="/cards/42" novalidate>
  <input type="hidden" name="_method" value="patch">
  ...
</form>
```

The browser does what it knows how to do (POST), but smuggles the real method along in the form body.

### What Proper Does on the Way In

Proper has a tiny request-pipeline step (`proper.pipeline.method_override`) that runs before routing.

It checks for `_method` and if it holds `PUT`, `PATCH`, `DELETE`, or `QUERY`, the request's method is rewritten before the router runs. The route definition `@router.patch("cards/:card_id")` matches the rewritten method, not the original `POST`.

This means your controller action sees a `PATCH` request and never has to know that the wire was actually `POST`.

:::note | Only POST gets overridden
The override step only runs for incoming `POST` requests. A `GET` is never rewritten, even if it happens to carry a `_method` parameter. This stops misbehaving links from triggering destructive actions.
:::

You usually don't think about method override at all. It just works.

---

## Render Helpers

Each field on a form exposes a set of methods that produce the right HTML for it:

Method                          | Renders
------------------------------- | ----------------------------------
`field.label(text=None)`        | `<label>` with the right `for` ID
`field.error_tag()`             | `<div id="<field-id>-error" class="field-error">` if there's an error
`field.text_input()`            | `<input type="text">`
`field.textarea()`              | `<textarea>`
`field.select(options)`         | `<select>` with options as `[(value, text), ...]`
`field.checkbox()`              | `<input type="checkbox">`
`field.radio(value)`            | `<input type="radio">`
`field.file_input()`            | `<input type="file">`
`field.email_input()`           | `<input type="email">`
`field.password_input()`        | `<input type="password">`
`field.date_input()`            | `<input type="date">`
`field.number_input()`          | `<input type="number">`

All of them accept `**attrs` for extra HTML attributes. Two name-conversion rules apply: `class_` is special-cased to `class` (so `class_="text-sm"` becomes `class="text-sm"`, working around the Python reserved word), and in every other attribute name each underscore becomes a hyphen (so `data_foo="bar"` becomes `data-foo="bar"`).

Required fields automatically get the `required` HTML attribute. Fields with errors get `aria-invalid="true"` and `aria-errormessage`. You don't have to add them yourself.

The full list of helpers (every input type, every option) is in the [Formidable field reference](https://formidable.scaletti.dev/docs/fields/#render-methods).

### The Field Pattern

Most fields end up wrapped in a small `<div>` with the same three pieces:

```html+jinja
<div class="field">
  {{ form.title.label("Title") }}
  {{ form.title.text_input() }}
  {{ form.title.error_tag() }}
</div>
```

Label, input, error tag - in that order. The error tag renders nothing when there's no error, so you can include it unconditionally.

If your design system needs a different wrapper, that's the only thing you need to change. The three render-helper calls stay the same regardless.

### Picking the Right Input Helper

The render helpers don't care about the field's *type* - a `TextField` can be rendered as a `<textarea>` or even a `<select>`, and an `IntegerField` can be rendered with `text_input()` if you want. The helper controls what HTML comes out; the field type controls validation and coercion on the way back in.

Some common pairings:

```html+jinja
{# Long text - render as a textarea #}
{{ form.body.textarea(rows=10) }}

{# Choice from a list - render as a select #}
{{ form.category.select([("book", "Book"), ("movie", "Movie")]) }}

{# Boolean flag - render as a single checkbox #}
{{ form.published.checkbox() }}

{# Date - render as a native date picker #}
{{ form.due_date.date_input() }}
```

For a checkbox or radio group, render the same field multiple times with different values:

```html+jinja
{{ form.size.radio("small") }}
{{ form.size.radio("medium") }}
{{ form.size.radio("large") }}
```

The helper compares the field's current value to the value you pass and adds `checked` if they match.

---

## Writing HTML by Hand

The helpers are convenient, not mandatory. Every field exposes the raw attributes you need to write the HTML yourself:

```html+jinja
<label for="{{ form.title.id }}">Title</label>
<input
  type="text"
  id="{{ form.title.id }}"
  name="{{ form.title.name }}"
  value="{{ form.title.value or '' }}"
  {% if form.title.error %}aria-invalid="true"{% endif %}
/>
{% if form.title.error %}
  <span class="field-error">{{ form.title.error_message }}</span>
{% endif %}
```

The four attributes you'll use most often are:

- `field.id` - the auto-generated DOM id, used to wire `<label for=...>`.
- `field.name` - the HTML form name. For plain fields it's the same as the Python attribute; for nested forms it's a bracketed path like `addresses[0][street]`.
- `field.value` - the current value (may be `None`).
- `field.error` and `field.error_message` - the error code and the human-readable message.

Reach for manual HTML when the helpers don't fit your design system, or when you need to render a field type the helpers don't cover (an autocomplete combobox, a custom date picker, a rich-text editor).

You can also mix the two: helpers for the standard cases, hand-written HTML for one custom field on the same form.

---

## The Generator's Layered Structure

The resource generator (`proper g resource`) sets up three layered Jx components for every form:

1. **`views/form.jx`** - the framework component that emits the `<form>` HTML tag, sets the action and method, and adds the hidden `_method` input for `PATCH`/`PUT`/`DELETE`.
2. **`views/<name>/form.jx`** - a per-resource component that lays out the fields. The generator writes this file for you.
3. **`views/<name>/new.jx` and `edit.jx`** - the pages, which import the per-resource form component and pass it the right action URL.

This split keeps the field markup in one place while giving you separate pages for creating and editing.

### The Per-Resource `form.jx`

For `proper g resource Card title:str body:text`, the generator writes `views/card/form.jx`:

```html+jinja
{#import "form.jx" as Form #}

{#js "js/nestedform.js" #}

{#def form, action='', method='post' #}

<Form method={{ method }} action={{ action }}>
  <div class="field">
    {{ form.title.label("Title") }}
    {{ form.title.text_input() }}
    {{ form.title.error_tag() }}
  </div>
  <div class="field">
    {{ form.body.label("Body") }}
    {{ form.body.text_input() }}
    {{ form.body.error_tag() }}
  </div>

  {{ content }}
</Form>
```

Three things to notice:

- `{#import "form.jx" as Form #}` pulls in the framework's `<Form>` component (from `views/form.jx`), which renders the actual `<form>` tag.
- `{#def form, action='', method='post' #}` declares the props this component takes: a Formidable form instance and the URL it submits to.
- `{{ content }}` is the slot where the page using this component (for example, `new.jx`) drops its submit button.

### The `new.jx` and `edit.jx` Pages

The generator pairs the form partial with two pages. `new.jx`:

```html+jinja
{#import "layouts/app.jx" as Layout #}
{#import "./form.jx" as CardForm #}

{#def form #}

<Layout title="New card">
  <CardForm
    action={{ url_for('Card.create') }}
    form={{ form }}
  >
    <button type="submit">Create card</button>
  </CardForm>
</Layout>
```

And `edit.jx`:

```html+jinja
{#import "layouts/app.jx" as Layout #}
{#import "./form.jx" as CardForm #}

{#def form, card #}

<Layout title="Edit card">
  <CardForm
    method="patch"
    action={{ url_for('Card.update', card) }}
    form={{ form }}
  >
    <button type="submit">Update card</button>
  </CardForm>
</Layout>
```

The only differences between the two are the action URL, the method (`patch` for update), and the button label. The field markup is shared.

### When to Break the Pattern

The shared partial is the right default, but it's not a rule. If the create flow needs more fields than the edit flow (think: a "send invite" toggle that only appears at signup), or if an admin form should look different from a public one, write a second component:

```
views/card/
├── form.jx              # public form
├── admin_form.jx        # admin form with extra fields
├── new.jx               # imports form.jx
├── edit.jx              # imports form.jx
└── admin_edit.jx        # imports admin_form.jx
```

The generator gives you the most common shape; diverging is fine when the forms genuinely differ.

---

## The Shape of Submitted Data

A browser only knows how to send flat key-value pairs. When you submit:

```html
<input name="title" value="Hello">
<input name="body" value="World">
```

what arrives at the server is:

```
title=Hello&body=World
```

That works for the simple case. But forms often need more structure: a list of tags, a nested settings object, a one-to-many relationship between a person and their addresses. HTML has a *naming convention* that lets you encode that structure in the `name` attribute, and Formidable's parser knows how to turn it back into nested Python data.

This section shows what happens between the browser and the form. Once you understand it, sub-forms and nested forms (in sections 8 and 9) are straightforward.

### Plain Fields

The basic case. One input, one value:

```html
<input name="title" value="Hello">
```

Wire format:

```
title=Hello
```

In the controller, `self.params["title"]` returns `"Hello"`. When you pass `self.params` to a form, `form.title.value` is `"Hello"`.

### Multiple Values for the Same Name

If two inputs have the same `name`, the browser sends both:

```html
<input type="checkbox" name="tags" value="python" checked>
<input type="checkbox" name="tags" value="ruby" checked>
<input type="checkbox" name="tags" value="go">
```

Wire format:

```
tags=python&tags=ruby
```

`self.params` is a `MultiDict`, so `self.params["tags"]` returns the *last* value (`"ruby"`) - which is wrong here. Use `self.params.getall("tags")` to get the full list `["python", "ruby"]`.

In a form, declare this with `f.ListField()`:

```python
class PostForm(f.Form):
    tags = f.ListField()
```

The list field consumes all the values that came in under `tags` and exposes them as a Python list:

```python
form.tags.value   # ["python", "ruby"]
```

You sometimes see the convention `name="tags[]"` (with empty brackets) to make it visually obvious that the field is multi-valued. Formidable accepts both forms.

### Nested Objects

Wrapping a name in brackets nests the value under a parent:

```html
<input name="user[name]" value="Jane">
<input name="user[email]" value="jane@example.com">
```

Wire format:

```
user[name]=Jane&user[email]=jane@example.com
```

`self.params` is still flat - `self.params["user[name]"]` is `"Jane"`. But when you pass it to a form, Formidable's parser turns the bracketed names into nested Python dictionaries:

```python
{
    "user": {
        "name": "Jane",
        "email": "jane@example.com",
    }
}
```

The form field that consumes this shape is `f.FormField` (covered in [Sub-forms with `FormField`](#sub-forms-with-formfield)).

### Lists of Objects

Combine the two: a number inside the first set of brackets, a name inside the second.

```html
<input name="addresses[0][street]" value="123 Main St">
<input name="addresses[0][city]"   value="Springfield">
<input name="addresses[1][street]" value="456 Oak Ave">
<input name="addresses[1][city]"   value="Shelbyville">
```

Wire format:

```
addresses[0][street]=123+Main+St&addresses[0][city]=Springfield&...
```

Formidable's parser produces a dict of dicts keyed by the grouping key (`"0"`, `"1"`, ...), not a list:

```python
{
    "addresses": {
        "0": {"street": "123 Main St", "city": "Springfield"},
        "1": {"street": "456 Oak Ave",  "city": "Shelbyville"},
    }
}
```

The final list shape only emerges later, after `f.NestedForms` processes those groups in `save()` - the parser itself never produces a list here. The form field for this shape is `f.NestedForms` (covered in [Nested Forms](#nested-forms)).

:::note | The numbers don't matter
The `0` and `1` in `addresses[0][...]` and `addresses[1][...]` are *grouping keys*, not list indices. They tell the parser "these inputs belong to the same sub-object." They don't have to start at zero, don't have to be sequential, and don't preserve order - they only have to be unique per sub-form. The dynamic JavaScript covered in ["Dynamic Add / Remove with JavaScript"](#dynamic) takes advantage of this by using arbitrary unique strings instead of numbers.
:::

### What Formidable Does With This

When you pass `self.params` (or any dict-like object) to a form constructor, Formidable runs all the keys through a parser. The parser:

- Treats `key` as a top-level value.
- Treats `key[]` as a list at the top level.
- Treats `key[name]` as a nested dict under `key`.
- Treats `key[N][name]` as a dict of dicts keyed by the grouping key `N` under `key` (the list shape only emerges later, in `NestedForms`/`save()`).

Each form field then reads from the corresponding place in the parsed structure. A `TextField` named `title` reads `parsed["title"]`. A `FormField` named `user` reads `parsed["user"]`. A `NestedForms` named `addresses` reads `parsed["addresses"]`.

You don't see any of this in your day-to-day code - the controller passes `self.params` to the form, the form parses it, and you read `form.<field>.value`. But understanding the wire format is what makes the rendering of sub-forms and nested forms click into place.

---

## Sub-forms with `FormField`

When a form has a one-to-one relationship with another form - a profile that has settings, a page that has metadata, a user that has a single billing address - the parent form embeds a sub-form via `f.FormField`. The Working with Forms guide covers [the declaration and what `save()` returns](/docs/forms#sub-forms-with-formfield); this section covers how to render it.

### The Markup

Inside the parent's template, the sub-form is reached through `field.form`:

```html+jinja
<div class="field">
  {{ form.name.label("Name") }}
  {{ form.name.text_input() }}
  {{ form.name.error_tag() }}
</div>

<fieldset>
  <legend>Settings</legend>
  <div class="field">
    {{ form.settings.form.locale.label("Locale") }}
    {{ form.settings.form.locale.text_input() }}
  </div>
  <div class="field">
    {{ form.settings.form.timezone.label("Timezone") }}
    {{ form.settings.form.timezone.text_input() }}
  </div>
</fieldset>
```

`form.settings` is the `FormField` field. `form.settings.form` is the embedded `SettingsForm` instance. From there, every render helper works exactly like on a top-level field.

### The Wire Format

The HTML names are `name`, `settings[locale]`, `settings[timezone]` - the bracket-nested structure from [Nested Objects](#nested-objects). When the user submits, Formidable's parser turns it into:

```python
{"name": "Jane", "settings": {"locale": "es_es", "timezone": "europe/madrid"}}
```

The parent form's `FormField` reads from `parsed["settings"]` and hands the dict to the sub-form, which validates and saves it just like any other form.

### Wrapping Conventions

There's no required wrapper around a sub-form's fields, but `<fieldset>` with a `<legend>` is the conventional choice - it's a semantic grouping element and screen readers understand it as "these inputs belong together."

---

## Nested Forms

When a form has a one-to-*many* relationship - a person with several addresses, a recipe with several ingredients, a poll with several options - the parent form embeds a list of sub-forms via `f.NestedForms`. The Working with Forms guide covers [the declaration, deletion, and `save()` shapes](/docs/forms#nested-forms); this section covers how to render them and the special hidden inputs they need.

The example for the rest of this section is a `Person` with many `Address` records:

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
    addresses = f.NestedForms(AddressForm)
```

### The Markup

Inside the parent's template, the nested field exposes a `forms` list - one sub-form instance per existing address:

```html+jinja
<Form action={{ url_for('Person.update', person) }} method="patch">
  <div class="field">
    {{ form.name.label("Name") }}
    {{ form.name.text_input() }}
    {{ form.name.error_tag() }}
  </div>

  <fieldset>
    <legend>Addresses</legend>

    {% for address in form.addresses.forms %}
      <div>
        {{ address.hidden_tags() }}
        <div class="field">
          {{ address.kind.label("Kind") }}
          {{ address.kind.text_input() }}
          {{ address.kind.error_tag() }}
        </div>
        <div class="field">
          {{ address.street.label("Street") }}
          {{ address.street.text_input() }}
          {{ address.street.error_tag() }}
        </div>
      </div>
    {% endfor %}
  </fieldset>

  <button type="submit">Save</button>
</Form>
```

`{{ address.hidden_tags() }}` is the new piece. It renders two hidden inputs that nested forms need: one named `_id` (the primary key of the existing object), and one named `_destroy` (a deletion marker). You'll see them in the rendered HTML below.

If a person has no addresses, the loop renders nothing. To start with a few empty sub-forms - useful on `new` so the user sees at least one set of fields - call `build()` on the field in the controller:

```python
def new(self):
    self.form.addresses.build(2)
```

### The Wire Format

With two empty addresses (from `build(2)`), the rendered HTML is:

```html
<input name="name" required>

<input type="hidden" name="addresses[0][_destroy]">
<input name="addresses[0][kind]" required>
<input name="addresses[0][street]" required>

<input type="hidden" name="addresses[1][_destroy]">
<input name="addresses[1][kind]" required>
<input name="addresses[1][street]" required>
```

The `0` and `1` are grouping keys, not list indices ([Lists of Objects](#lists-of-objects) covered why). The `_id` hidden input only appears when the form was instantiated with existing addresses; the `_destroy` input only appears when deletion is allowed (`allow_delete=True` on the field).

When the user submits, Formidable's parser turns this into a dict of dicts keyed by the grouping key:

```python
{
    "name": "Jane",
    "addresses": {
        "0": {"kind": "home", "street": "..."},
        "1": {"kind": "work", "street": "..."},
    },
}
```

`PersonForm` reads from the parsed structure and builds (or updates) the right model instances; `NestedForms` collapses those groups into the final list of sub-forms.

:::warning | The `_id` hidden field is safe
A user can edit the `_id` value in DevTools to point at someone else's record - and Formidable will silently ignore the change. The form remembers which objects it was instantiated with, and any `_id` that doesn't match one of those is rejected. Users cannot update objects they aren't authorized to modify just by editing the HTML.
:::

### What `hidden_tags()` Renders

`address.hidden_tags()` renders zero, one, or two `<input type="hidden">` tags depending on the situation:

| Form was built with... | `allow_delete`? | What renders                      |
| ---------------------- | --------------- | --------------------------------- |
| no existing object     | `False`         | nothing                           |
| no existing object     | `True`          | `_destroy` only                   |
| existing object        | `False`         | `_id` only                        |
| existing object        | `True`          | both `_id` and `_destroy`         |

You don't need to read this table to render correctly - just always include `{{ address.hidden_tags() }}` inside each sub-form's wrapper, and the right inputs will appear automatically.

---

## Dynamic Add / Remove with JavaScript
{id="dynamic"}

So far we've shown a fixed number of sub-forms. The interesting case is letting users add and remove them in the browser. That's a JavaScript problem, but Formidable ships a small vanilla-JS file (`nestedform.js`) that handles it for you, and the resource generator already includes it.

The rest of this section walks through what's in the file and how to wire a sub-form to it. The example: a to-do list, where users can add new items, remove them, and edit existing ones.

### Step 1. The script

The generator's `form.jx` already includes:

```html+jinja
{#js "js/nestedform.js" #}
```

`{#js #}` is a Jx directive that adds the script to the page's `<head>`. The file lives in your app's `assets/js/` directory, alongside the rest of your front-end code. If you wrote the controller by hand and don't have the file, copy it from the [Formidable repository](https://github.com/jpsca/formidable/blob/main/src/formidable/nestedform.js).

### Step 2. The forms

```python
# myapp/forms/todo.py
from proper import forms as f


class TodoForm(f.Form):
    description = f.TextField(required=True)


class TodoListForm(f.Form):
    todo = f.NestedForms(TodoForm, allow_delete=True)
```

Use a Jinja macro to render a single sub-form so the same markup works for both the existing items (in the loop) and the template (for new items):

```html+jinja
{% macro render_todo(form, label) -%}
<div>
  {{ form.description.label(label) }}
  {{ form.description.text_input() }}
  {{ form.description.error_tag() }}
  {{ form.hidden_tags() }}
</div>
{%- endmacro %}

<form method="post">
  {% for todo_form in form.todo.forms %}
    {{ render_todo(todo_form, "Your todo") }}
  {% endfor %}
</form>
```

This is still a static version - we'll add the dynamic parts next.

### Step 3. Mark the form

Add `data-nestedform` to the form (or any wrapper element). This tells the JavaScript "everything inside here is a nested form."

```html+jinja
<form method="post" data-nestedform>
  ...
</form>
```

### Step 4. Mark each sub-form

Give each sub-form wrapper the CSS class `nestedform`:

```html+jinja
{% macro render_todo(form, label) -%}
<div class="nestedform">
  {{ form.description.label(label) }}
  ...
</div>
{%- endmacro %}
```

### Step 5. The remove button

Add a button with `data-nestedform-remove` inside each sub-form. Clicking it marks the sub-form for deletion (by filling the `_destroy` hidden input) and hides it from view.

```html+jinja
{% macro render_todo(form, label) -%}
<div class="nestedform">
  {{ form.description.label(label) }}
  <div class="field">
    {{ form.description.text_input() }}
    <button type="button" data-nestedform-remove title="Remove todo">&times;</button>
  </div>
  {{ form.description.error_tag() }}
  {{ form.hidden_tags() }}
</div>
{%- endmacro %}
```

### Step 6. The template

Add a `<template>` element with `data-nestedform-template` *inside* the `data-nestedform` element. The script clones this template every time the user adds a new sub-form:

```html+jinja
<form method="post" data-nestedform>
  {% for todo_form in form.todo.forms %}
    {{ render_todo(todo_form, "Your todo") }}
  {% endfor %}

  <template data-nestedform-template>
    {{ render_todo(form.todo.empty_form, "New todo") }}
  </template>
</form>
```

`form.todo.empty_form` is a special attribute on `NestedForms` that returns an empty sub-form instance, intended for exactly this use. The script gives each clone a unique grouping key in its `name` attributes.

### Step 7. The insertion point

The script needs to know *where* to put new sub-forms. Add an empty element with `data-nestedform-target` (also inside the `data-nestedform` element):

```html+jinja
<form method="post" data-nestedform>
  ...
  <div data-nestedform-target></div>
</form>
```

### Step 8. The add button

Finally, a button to trigger the insertion:

```html+jinja
<form method="post" data-nestedform>
  ...
  <div data-nestedform-target></div>
  <button type="button" data-nestedform-add>Add todo</button>
</form>
```

### Step 9. Putting it all together

The complete partial:

```html+jinja
{% macro render_todo(form, label) -%}
<div class="nestedform">
  {{ form.description.label(label) }}
  <div class="field">
    {{ form.description.text_input() }}
    <button type="button" data-nestedform-remove title="Remove todo">&times;</button>
  </div>
  {{ form.description.error_tag() }}
  {{ form.hidden_tags() }}
</div>
{%- endmacro %}

<form method="post" data-nestedform>
  {% for todo_form in form.todo.forms %}
    {{ render_todo(todo_form, "Your todo") }}
  {% endfor %}

  <template data-nestedform-template>
    {{ render_todo(form.todo.empty_form, "New todo") }}
  </template>

  <div data-nestedform-target></div>

  <button type="button" data-nestedform-add>Add todo</button>
  <button type="submit">Save</button>
</form>
```

Six data attributes (`data-nestedform`, `data-nestedform-template`, `data-nestedform-target`, `data-nestedform-add`, `data-nestedform-remove`) and one CSS class (`.nestedform`) - that's the entire surface area of the script.

---

## File Upload Forms

A form that lets the user upload a file needs three pieces:

1. The `<Form>` tag with `multipart=True` so the browser sends the file bytes, not just the filename.
2. A `FileField` on the form to validate that something was uploaded.
3. A render helper for the file input.

### The Form

```python
from proper import forms as f


class AvatarForm(f.Form):
    avatar = f.FileField()
    caption = f.TextField(required=False)
```

`FileField` is a *validation* field - it checks that the user actually attached a file (when `required=True`, the default). It does not move the file, store it, or expose its bytes. For that, see the [File Storage guide](/docs/storage), which covers attaching files to model records, storing them on disk or S3, and serving them back safely.

:::tip | Use `AttachmentField` for model-bound uploads
When the upload should land on a model column (a user's avatar, a book's cover image), reach for [`f.AttachmentField`](/docs/forms#attachmentfield) instead of `f.FileField`. `AttachmentField` saves the file through the storage service, INSERTs the `Attachment` row, and assigns the FK from inside `form.save()` - no controller plumbing needed. Its render helpers are covered in [Attachment Uploads](#attachment-uploads) below.
:::

### The Markup

```html+jinja
<Form
  multipart
  action={{ url_for('User.update_avatar') }}
  method="patch"
>
  <div class="field">
    {{ form.avatar.label("Avatar") }}
    {{ form.avatar.file_input(accept="image/*") }}
    {{ form.avatar.error_tag() }}
  </div>
  <div class="field">
    {{ form.caption.label("Caption") }}
    {{ form.caption.text_input() }}
  </div>
  <button type="submit">Save</button>
</Form>
```

Two things to notice:

- **`multipart`** on the `<Form>` tag. Without it, the browser still renders the file input but submits only the filename. The bytes never leave the user's machine.
- **`accept="image/*"`** restricts the file picker to image types. The browser uses this as a hint; it's not enforcement, so always re-validate on the server. For attachment-bound uploads, [`AttachmentField`'s `accept` and `max_size`](/docs/forms#validating-uploads) arguments use the same pattern syntax to enforce the same rule server-side.

The HTML the component produces:

```html
<form method="patch" action="/users/42/avatar" enctype="multipart/form-data" novalidate>
  <input type="hidden" name="_method" value="patch">
  <label for="..."> Avatar </label>
  <input type="file" id="..." name="avatar" accept="image/*" required>
  ...
</form>
```

### Handling the Upload

In the controller, the uploaded file arrives in `self.request.form` (not a `FileField` value):

```python
def update_avatar(self):
    upload = self.request.form.get("avatar")
    if upload:
        # upload.filename, upload.content_type, upload.read(), upload.save(...)
        ...
```

The Storage guide covers turning that upload into an `Attachment` model record. For one-off cases, `upload.save("/path/to/destination")` works.

### Multiple Files

For multi-file uploads, add the `multiple` HTML attribute and use `params.getall(...)` to read all uploads:

```html+jinja
{{ form.photos.file_input(accept="image/*", multiple=True) }}
```

```python
def upload(self):
    photos = self.request.form.getall("photos")
    for photo in photos:
        # process each upload
        ...
```

### Attachment Uploads

When the upload is bound to a model column via [`f.AttachmentField`](/docs/forms#attachmentfield), the field exposes two render helpers instead of the single `file_input()` you'd use for `FileField`:

```html+jinja
<Form
  multipart
  method="patch"
  action={{ url_for('Book.update', book_id=book.id) }}
>
  <div class="field">
    {{ form.cover.label("Cover") }}
    {{ form.cover.file_input(accept="image/*") }}
    {{ form.cover.destroy_input() }}
    {{ form.cover.error_tag() }}
  </div>
  <button type="submit">Save</button>
</Form>
```

The two helpers produce two `<input>` tags that share the field's bracketed name:

- **`field.file_input(**attrs)`** - renders `<input type="file" name="<field>[file]">`. The `value` attribute is intentionally omitted (browsers ignore it on file inputs anyway). When the field is bound to an existing attachment, the `required` attribute is dropped so the user doesn't have to re-upload to submit the form.
- **`field.destroy_input(**attrs)`** - renders `<input type="hidden" name="<field>[_destroy]" value="0">`. This is the flag your "Remove" button toggles to `"1"` from JavaScript when the user wants to clear the attachment without uploading a replacement. The `_destroy` convention mirrors the one [nested forms use](/docs/forms#nested-forms) for deletions.

The `multipart` attribute on `<Form>` is still required - without it, the file bytes never leave the browser.

The field declaration on the form side is where you set server-side limits like `max_size` and `accept`; rejected uploads surface as ordinary field errors and render through the same `error_tag()`. The `accept` argument uses the same pattern syntax as the HTML `accept` attribute, so the file-picker hint and the server-side validator can share patterns. See [Working with Forms - Validating uploads](/docs/forms#validating-uploads).

#### The behavior matrix

| User did              | `<field>[file]` | `<field>[_destroy]` | Action on `form.save()`                         |
| --------------------- | --------------- | ------------------- | ----------------------------------------------- |
| Uploaded a new file   | populated       | (any)               | save new attachment, purge the previous one     |
| Clicked "Remove"      | empty           | `"1"`               | clear the FK, purge the previous attachment     |
| Left the field alone  | empty           | `"0"` or absent     | preserve the existing attachment                |

#### The drop-in image input

`proper install storage` ships a Jx component that wires the two inputs together with drag-and-drop, an existing-attachment preview, and a "Remove" button that toggles `_destroy` for you:

```html+jinja
{#import "image_input.jx" as ImageInput #}

<ImageInput field={{ form.cover }} />
```

For non-image attachments (PDFs, audio, video), or for designs that need a different layout, write the markup with `file_input()` and `destroy_input()` directly.

---

## Forms to External URLs

Most of the time, your forms post back to your own controllers, and the `<Form>` component is the right choice. Occasionally, you'll need a form that posts to a different host - signing up to a third-party newsletter, redirecting to a payment provider, hitting a webhook test endpoint.

For these cases, use a plain `<form>` tag instead of the `<Form>` component:

```html+jinja
<form method="post" action="https://api.example.com/subscribe">
  <input type="email" name="email" required>
  <button type="submit">Subscribe</button>
</form>
```

Two reasons not to reach for the `<Form>` component here:

- **Method override won't work.** A `<Form method="patch">` adds a hidden `_method` input, expecting Proper's request layer to rewrite the method. The external server has no idea what `_method` means and will see a `POST`.
- **Field render helpers don't apply.** The whole point of the helpers is that they're attached to a Formidable form object. For an external endpoint, you're constructing the request body to match the *external* service's expectations, not your own form's.

If you need labels, errors, or pre-filled values, write the HTML manually - this is fundamentally a different kind of form, even if it looks similar.

:::warning | CSRF and external POSTs
Posting from your page to a third-party server is *not* covered by Proper's CSRF protection (which only guards your own endpoints). Make sure the third-party endpoint either accepts cross-origin POSTs intentionally (most public APIs do) or that you have an arrangement that authenticates the request another way (a signed token in a hidden field, a server-to-server call instead of a browser form).
:::

---

## What's Next

Now that you've seen the rendering side, the rest of the form story is in two places:

- [Working with Forms](/docs/forms) - declaring forms, the four instantiation patterns, validation, error messages, saving, testing.
- [Formidable documentation](https://formidable.scaletti.dev/) - the full field reference, every render helper, every option.

For specific topics adjacent to forms:

- [File Storage](/docs/storage) - the `Attachment` model behind `AttachmentField`, image variants, served files, and signed URLs for private uploads.
- [Internationalization (i18n)](/docs/i18n) - translating field labels, error messages, and the `<legend>` text in nested forms.
