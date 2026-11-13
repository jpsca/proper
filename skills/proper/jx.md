---
title: Jx Components
description: Component template system — syntax, imports, props, content and slots, attrs, component assets, SVG icons
last_verified: 2026-11-13
sources:
  - src/proper/views
---

# Jx Components

Jx is a component-based template system with Jinja's syntax. Components are `.jx` files with explicit imports, prop declarations, and an HTML-like call syntax. Proper compiles each component to a Python function at startup, with its own compiler (`jxc`, in `proper/_native/`; the runtime is `proper.views`).

**Syntax available:** `{{ }}`, `if`/`elif`/`else`, `for` (with `loop`, `else`, `recursive`), `set name = value`, `do`, `raw`, `filter`, `macro`, Jinja's builtin filters (except `xmlattr`, `pprint`, `urlize`) and tests, custom filters and tests, and block tags: Proper's `{% cache %}`, `{% frame %}`, `{% stream %}`.
**Not available:** `include`, `extends`, `block` (use components and layouts), `with`, `call`, block `set`, `namespace()`, imports with a `@prefix/`, Jinja extensions.

**Escaping:** `{{ }}` escapes in `.jx`, `.html.jx` and `.xml.jx` files, unless the value is markup (a component's output, `attrs.render()`, form fields, `| safe`). Other files (`.txt.jx`, `.json.jx`) render values as they are.
**Names:** a name that is not an argument, a `set` variable, a loop variable or a global is a `KeyError` (with a note saying where it was looked for), except in `| default(...)` and `is defined`. Arguments that the `{#def}` doesn't declare are only in `attrs`. A `set` of a new name inside a `for` is not visible after the loop; a `set` of a name that already exists changes it (there is no loop scope, unlike Jinja). Inside a `{% fill %}`, a macro or a block tag's body, a `set` never changes the outer value.

Component JavaScript is a Stimulus controller declared with `{#js #}`, never inline vanilla JavaScript: see [frontend.md, Stimulus](frontend.md#stimulus). The standalone `jx` skill, when installed, has UI component patterns (buttons, modals, dropdowns); its library mechanics (`jx.Catalog`) are the standalone package's, while a Proper app uses `app.catalog` ([reference/jx_catalog.md](reference/jx_catalog.md)).

## Table of Contents

- [Components](#components)
- [Imports](#imports)
- [Arguments (Props)](#arguments-props)
- [Content & Slots](#content--slots)
- [Attrs](#attrs)
- [Assets](#assets)
- [SVG Icon Patterns](#svg-icon-patterns)
- [Layouts and the Catalog](#layouts-and-the-catalog)


## Components

A component is a `.jx` file with optional props, imports, assets, and template content.

### Anatomy

```html+jinja
{#import "./header.jx" as Header #}
{#css card.css #}
{#js card.js #}
{#def title, subtitle="" #}

<div class="card">
  <Header title={{ title }} subtitle={{ subtitle }} />
  <div class="card-body">
    {{ content }}
  </div>
</div>
```

From top to bottom:

1. **Imports** — other components this one uses
2. **Assets** — CSS and JS files
3. **Arguments** — data the component accepts (`{#def ...#}`)
4. **Template** — the HTML to render

All parts are optional except the template.


### Using Components

Import a component, then use it like an HTML tag:

```html+jinja
{#import "card.jx" as Card #}
{#import "button.jx" as Button #}

<Card title="Welcome">
  <p>Hello world!</p>
  <Button text="Click me" />
</Card>
```

**Block syntax** for components with content:

```html+jinja
<Card title="Hello">
  <p>Content goes here</p>
</Card>
```

**Self-closing syntax** for components without content:

```html+jinja
<Button text="Click me" />
```


## Imports

```html+jinja
{#import "path/to/component.jx" as Name #}
```

The import alias must be **PascalCase** to distinguish components from HTML tags.

### Absolute Imports

Paths relative to a catalog folder. Use for shared components used across your project:

```html+jinja
{#import "layouts/app.jx" as Layout #}
{#import "nav.jx" as Nav #}
```

### Relative Imports

Paths relative to the current file. Use for tightly related components that live in the same directory:

```html+jinja
{#import "./sibling.jx" as Sibling #}
{#import "../parent/component.jx" as Component #}
```

Relative imports cannot go outside the catalog folder. Moving an entire folder preserves internal imports.

Component files can use any naming convention: `button.jx`, `user-card.jx`, `form_input.jx`, etc.:

```html+jinja
{#import "user-card.jx" as UserCard #}
{#import "form_input.jx" as FormInput #}
```


## Arguments (Props)

### Declaring

Use `{#def ...#}` at the top of a component:

```html+jinja
{#def title, count=0, active=true, items=[] #}

<h2>{{ title }}: {{ count }}</h2>
```

- `title` — required (no default)
- `count` — optional (defaults to `0`)

Defaults are Python expressions: strings, numbers, booleans, lists, dicts, etc. They can't use globals or other names, except `len`, `max`, `min`, `pow` and `sum` (a compile error). A default that is not a plain literal (`tags=[]`, `config={"a": [1]}`) is **evaluated again at every render**, so it is never shared between renders, nested values included.

For components with many arguments, `{#def}` can span multiple lines:

```html+jinja
{#def
    title: str,
    count: int = 0,
    items: list = [],
    config: dict = {}
#}
```

Arguments can have type annotations for runtime validation of built-in types:

```html+jinja
{#def title: str, count: int = 0 #}
```

When the annotation resolves to a Python built-in (`int`, `str`, `bool`, `list`, `dict`, `tuple`, `set`, `frozenset`, `float`, `complex`, `bytes`, `bytearray`, `memoryview`, `range`, `slice`, `type`), Jx runs `isinstance(value, expected_type)` at render time (the default value too) and raises `InvalidPropType` (a `TypeError`) on a mismatch. Type checking is **shallow**: for `list[str]`, only the outer `list` is checked; the elements are not inspected. The same applies to `dict[str, int]`.

Annotations that don't resolve to a built-in — custom classes, unions like `int | str`, `Optional[int]`, `typing.Iterable[str]` — are not checked, nor evaluated: they are kept as text in the signature of the compiled function. Stick to built-ins for strict checking; drop the annotation when you need a permissive shape.

When the views compile, each component call is checked against the component's signature: a missing required argument (`<Card />`), or a literal of the wrong type (`<Card count="3" />` for `count: int`; a flag like `<Card open />` is `True`), is a compile error with file, line and column. These errors don't stop the file: every one of them is reported (and the module isn't written); a syntax error or an import that doesn't resolve stops the file there. Values computed at render time are checked then. `proper check` also checks the literal route names of `url_for` calls in the views (read from the compiled modules, mapped to the template line with `LINEMAP`).

### Passing Arguments

**Strings** use quotes:

```html+jinja
<Button text="Click me" />
```

**Expressions** use `{{ }}`:

```html+jinja
<Card user={{ current_user }} count={{ items | length }} active={{ true }} />
```

Lists, dicts, and other Python literals work as expressions:

```html+jinja
<Card items={{ [1, 2, 3] }} config={{ {"key": "value"} }} />
```

**Booleans** — HTML-style shorthand for `true`:

```html+jinja
<Input required />          {# Same as required={{ true }} #}
<Input disabled={{ false }} />   {# Explicitly false #}
```

**Dashes to underscores** — dashes in attribute names convert to underscores:

```html+jinja
{#def aria_label, data_id #}

<Button aria-label="Close" data-id="123" />
```


## Content & Slots

### The `content` Variable

Everything between a component's tags is available as `content`:

```html+jinja
{#def title #}

<div class="card">
  <h3>{{ title }}</h3>
  <div class="body">{{ content }}</div>
</div>
```

Fallback when no content is passed:

```html+jinja
{{ content or "No content provided" }}
```

### Named Slots

For multiple content areas, define slots with `{% slot %}` and fill them with `{% fill %}`:

```html+jinja
{# Component definition #}
<div class="modal">
  <div class="modal-header">
    {% slot header %}
      <h3>Default Header</h3>
    {% endslot %}
  </div>
  <div class="modal-body">
    {{ content }}
  </div>
  <div class="modal-footer">
    {% slot footer %}
      <button>Close</button>
    {% endslot %}
  </div>
</div>
```

```html+jinja
{# Usage #}
<Modal>
  {% fill header %}
    <h3>Confirm</h3>
  {% endfill %}

  <p>Are you sure?</p>

  {% fill footer %}
    <button>Yes</button>
    <button>No</button>
  {% endfill %}
</Modal>
```

Unfilled slots use their default content.

### When to Use What

- **Use props** when the content is a single value and you want validation.
- **Use `content`** when the content is HTML and there's one main content area.
- **Use named slots** when you need multiple content areas, each with a specific purpose and optional defaults.


## Attrs

The `attrs` object collects any HTML attributes passed to a component that aren't declared in `{#def}`. It enables flexible, forwardable HTML attributes.

### How It Works

1. Declared arguments (from `{#def}`) are extracted and available as variables.
2. Everything else goes into the `attrs` object.
3. You call `attrs.render()` to output them as HTML attributes.

For example, given `{#def text #}` and `<Button text="Save" id="save-btn" class="primary" />`, `text` becomes a variable while `id` and `class` go into `attrs`.

An attribute name with a space, a quote, `<`, `>`, `/`, `=` or a control character raises `ValueError` (from `Attrs(...)`, `set()`, `setdefault()` and `render()`), so a name that comes from data (`attrs={{ {key: value} }}`) can't break out of the tag. Values are always quoted and escaped, except `Markup`.

### Basic Usage

```html+jinja
{#def text #}

<button {{ attrs.render(class="btn", type="button") }}>
  {{ text }}
</button>
```

```html+jinja
<Button text="Save" id="save-btn" disabled data-action="save" />
```

Renders as:

```html
<button class="btn" data-action="save" id="save-btn" type="button" disabled>Save</button>
```

### Class Merging

The `class` attribute is special — it **merges** instead of replacing:

```html+jinja
{#def text #}
<button {{ attrs.render(class="btn") }}>{{ text }}</button>
```

```html+jinja
<Button text="Save" class="btn--primary" />
```

Renders: `<button class="btn btn--primary">Save</button>`

Duplicate classes are automatically skipped.

### Underscore to Dash Conversion

Underscores in attribute names are converted to dashes when rendered. This is useful for `data-*`, `aria-*`, and framework-specific attributes:

```html+jinja
<Button data_user_id="123" aria_label="Save" hx_get="/api/save" />
```

Renders attributes as `data-user-id`, `aria-label`, `hx-get`.

### Methods

| Method | Description |
|--------|-------------|
| `attrs.render(**kw)` | Render all attributes as an HTML string. Extra kwargs are merged (their classes go before the ones passed to the component, others override). `True` = boolean attr, `False` = remove, underscores become dashes. |
| `attrs.set(**kw)` | Modify attributes before rendering. Classes are added after the existing ones, not replaced; others override. |
| `attrs.setdefault(**kw)` | Set attributes only if not already present. |
| `attrs.get(name, default=None)` | Get the value of an attribute. |
| `attrs.add_class(*classes)` | Add one or more classes. |
| `attrs.remove_class(*classes)` | Remove one or more classes. |
| `attrs.prepend_class(*classes)` | Add classes to the beginning of the class list. |
| `attrs.classes` | Property. Returns all HTML classes as a space-separated string. |
| `attrs.as_dict` | Property. Returns all attributes as a dictionary. |

You can also use the alias `classes` instead of `class` if needed (e.g., to avoid Python's `class` keyword).

### Template Examples

**Conditional styling with `attrs.set()`:**

```html+jinja
{#def title, highlighted=false #}

{% if highlighted %}
  {% do attrs.set(class="card-highlighted", role="alert") %}
{% endif %}

<div {{ attrs.render(class="card") }}>
  <h3>{{ title }}</h3>
  {{ content }}
</div>
```

**Defaults with `attrs.setdefault()`:**

```html+jinja
{% do attrs.setdefault(role="button", tabindex=0) %}
<div {{ attrs.render(class="btn") }}>{{ content }}</div>
```

**Extracting a specific attribute:**

```html+jinja
{%- set btn_type = attrs.get("type", "button") %}
<button {{ attrs.render(type=btn_type) }}>{{ content }}</button>
```

**Adding/removing classes:**

```html+jinja
{% do attrs.add_class("btn", "btn--primary") %}
{% do attrs.remove_class("hidden") %}
<button {{ attrs.render() }}>{{ content }}</button>
```

### Forwarding Attrs to Child Components

Pass `attrs` explicitly as an argument:

```html+jinja
{#import "./button.jx" as Button #}
{#def text #}

<div class="button-wrapper">
  <Button text={{ text }} attrs={{ attrs }} />
</div>
```

Do **not** use `{{ attrs.render() }}` on component tags — it is a compile error. Pass them with `attrs={{ attrs }}`.

### Best Practices

1. Always provide default classes in `attrs.render(class="btn")` so the component has sensible styles even when no class is passed.
2. Use `setdefault` for semantic attributes like `role` and `tabindex`.
3. Document expected attrs in a comment at the top of the component.
4. Batch `attrs.set()` calls rather than calling it multiple times.


## Assets

Components can declare CSS and JavaScript dependencies:

```html+jinja
{#css card.css, animations.css #}
{#js card.js #}
{#def title #}

<div class="card">{{ content }}</div>
```

Multiple files are comma-separated.

### Asset URL Types

Asset paths can be:

- **Relative**: `card.css` — kept as written; the layout passes it through `url_for('assets', file=url)`
- **Absolute path**: `/assets/css/global.css`
- **Full URL**: `https://cdn.example.com/library.js`

Jx doesn't process or rewrite asset URLs; they're collected exactly as you write them. The generated layout passes every one through `url_for('assets', file=url)`, so with it only paths relative to `assets/` work; for an absolute path or a full URL, change the layout's loop.

### Collecting Assets

In the layout, use `assets.collect_css()` and `assets.collect_js()` to get the URLs declared by the page's component and all the components it imports:

```html+jinja
{% for url in assets.collect_css() %}
  <link rel="stylesheet" href="{{ url_for('assets', file=url) }}">
{% endfor %}

{% for url in assets.collect_js() %}
  <script src="{{ url_for('assets', file=url) }}" type="module"></script>
{% endfor %}
```

Assets are collected by walking the component tree, deduplicated, and returned in dependency order: parent component assets first, then imported component assets, in import order. If multiple components declare the same CSS file, it's only included once.

### Render Helpers

These write the URLs as declared, with no `url_for`: use them only with absolute paths or full URLs. The generated layout uses the `collect_*` loops instead ([frontend.md](frontend.md#component-assets)).

For simpler cases:

```html+jinja
{{ assets.render() }}          {# Both CSS and JS #}
{{ assets.render_css() }}      {# Only <link> tags #}
{{ assets.render_js() }}       {# Only <script> tags (type="module" by default) #}
```

`render_js()` accepts parameters to control script loading:

```html+jinja
{{ assets.render_js() }}                              {# <script type="module" src="..."> #}
{{ assets.render_js(module=false) }}                  {# <script src="..." defer> (defer is on by default) #}
{{ assets.render_js(module=false, defer=false) }}     {# <script src="..."> #}
```

### CSS Scoping

Jx does not scope CSS automatically. Use BEM-style naming or CSS nesting to avoid style collisions between components:

```css
/* Good — scoped to the component */
.Card {
  padding: 1rem;
  & h3 { font-size: 1.5rem; }
}

/* Bad — affects all h3 elements globally */
h3 { font-size: 1.5rem; }
```


## SVG Icon Patterns

### Basic Icon Component

```html+jinja
{#def size=24 #}

<svg {{ attrs.render(class="icon") }}
  xmlns="http://www.w3.org/2000/svg"
  width="{{ size }}" height="{{ size }}"
  viewBox="0 0 24 24"
  fill="none" stroke="currentColor"
  stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
>
  {{ content }}
</svg>
```

Using `currentColor` for stroke/fill lets icons inherit the text color of their parent.

### Icon Button

Combine an icon with a button, ensuring accessibility:

```html+jinja
{#import "./icon.jx" as Icon #}
{#def label="" #}

{% do attrs.setdefault(type="button") %}
{% do attrs.set(aria_label=label if label else None) %}
<button {{ attrs.render(class="btn btn--icon") }}>
  {{ content }}
</button>
```

```html+jinja
<IconButton label="Close">
  <Icon size={{ 16 }}>&times;</Icon>
</IconButton>
```

Tips:
1. Use `currentColor` for fill/stroke to inherit text color
2. Set sensible defaults for size (24px)
3. Add `aria-hidden="true"` for decorative icons
4. Use `aria-label` on icon-only buttons


## Layouts and the Catalog

Layout components (slots, nesting, navigation highlighting) are in [frontend.md](frontend.md#layouts). The `Catalog` class (`app.catalog`: globals, filters, block tags, `render()`) is in [reference/jx_catalog.md](reference/jx_catalog.md).
