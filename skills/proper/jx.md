---
title: Jx Components
description: Component template system — imports, props, slots, attrs, assets, htmx, Catalog API
last_verified: 2026-09-28
---

# Jx Components

Jx is a component-based template system with Jinja's syntax. Components are `.jx` files with explicit imports, prop declarations, and an HTML-like call syntax. Proper compiles each component to a Python function with [minijx](https://github.com/jpsca/minijx), at startup.

**Syntax available:** `{{ }}`, `if`/`elif`/`else`, `for` (with `loop`, `else`, `recursive`), `set name = value`, `do`, `raw`, `filter`, `macro`, Jinja's builtin filters (except `xmlattr`, `pprint`, `urlize`) and tests, custom filters and tests, and block tags: Proper's `{% cache %}`, `{% turbo_frame %}`, `{% turbo_stream %}`.
**Not available:** `include`, `extends`, `block` (use components and layouts), `with`, `call`, block `set`, `namespace()`, imports with a `@prefix/`, Jinja extensions.

**Escaping:** `{{ }}` escapes in `.jx`, `.html.jx` and `.xml.jx` files, unless the value is markup (a component's output, `attrs.render()`, form fields, `| safe`). Other files (`.txt.jx`, `.json.jx`) render values as they are.
**Names:** a name that is not an argument, a `set` variable, a loop variable or a global is a `KeyError` (with a note saying where it was looked for). A `set` inside a `for` is not visible after the loop.

> For production UI component patterns (buttons, modals, dropdowns, form inputs, layouts, etc.), see the **jx-components** skill. Component JavaScript should use **StimulusJS**, not vanilla JavaScript. Bare imports like `@hotwired/stimulus` are resolved by the [import maps](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/script/type/importmap). Every Stimulus controller must self-register via `window.Stimulus.register()`:
>
> ```js
> // toast_controller.js
> import { Controller } from "@hotwired/stimulus";
>
> export default class ToastController extends Controller {
>   static values = {
>     duration: { type: Number, default: 5000 },
>   };
>
>   connect() {
>     if (this.durationValue > 0) {
>       this.timeout = setTimeout(() => this.dismiss(), this.durationValue);
>     }
>   }
>
>   disconnect() {
>     clearTimeout(this.timeout);
>   }
>
>   dismiss() {
>     clearTimeout(this.timeout);
>     this.element.style.opacity = "0";
>     this.element.style.transform = "translateX(100%)";
>     setTimeout(() => this.element.remove(), 300);
>   }
> }
> window.Stimulus.register("toast", ToastController);
> ```

## Table of Contents

- [Components](#components)
- [Imports](#imports)
- [Arguments (Props)](#arguments-props)
- [Content & Slots](#content--slots)
- [Attrs](#attrs)
- [Assets](#assets)
- [Layout Patterns](#layout-patterns)
- [SVG Icon Patterns](#svg-icon-patterns)
- [Working with htmx](#working-with-htmx)
- [Catalog API](#catalog-api)


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

Defaults are Python expressions: strings, numbers, booleans, lists, dicts, etc. A default that is not a plain literal (`tags=[]`, `config={"a": [1]}`) is **evaluated again at every render**, so it is never shared between renders, nested values included.

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

When the annotation resolves to a Python built-in (`int`, `str`, `bool`, `list`, `dict`, `tuple`, `set`, `float`, `bytes`), Jx runs `isinstance(value, expected_type)` at render time (the default value too) and raises `InvalidPropType` (a `TypeError`) on a mismatch. Type checking is **shallow**: for `list[str]`, only the outer `list` is checked; the elements are not inspected. The same applies to `dict[str, int]`.

Annotations that don't resolve to a built-in — custom classes, unions like `int | str`, `Optional[int]`, `typing.Iterable[str]` — are not checked, nor evaluated: they are kept as text in the signature of the compiled function. Stick to built-ins for strict checking; drop the annotation when you need a permissive shape.

When the views compile, each component call is checked against the component's signature: a missing required argument (`<Card />`), or a literal of the wrong type (`<Card count="3" />` for `count: int`; a flag like `<Card open />` is `True`), is a compile error with file, line and column. Values computed at render time are checked then.

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
<button class="btn" id="save-btn" data-action="save" type="button" disabled>Save</button>
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
| `attrs.render(**kw)` | Render all attributes as an HTML string. Extra kwargs are merged (classes appended, others override). `True` = boolean attr, `False` = remove, underscores become dashes. |
| `attrs.set(**kw)` | Modify attributes before rendering. Same merging rules as `render()`. Classes are appended, not replaced. |
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
<button {{ attrs.render() }} type="{{ btn_type }}">{{ content }}</button>
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

Do **not** use `{{ attrs.render() }}` on component tags — it won't work. Component tags are preprocessed before rendering.

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

- **Relative**: `card.css` — resolved relative to the assets folder
- **Absolute path**: `/assets/css/global.css`
- **Full URL**: `https://cdn.example.com/library.js`

Jx doesn't process or rewrite asset URLs; they're used exactly as you write them.

### Collecting Assets

In the layout, use `assets.collect_css()` and `assets.collect_js()` to get the URLs declared by all components used on the page:

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


## Layout Patterns

### Basic Layout

A layout is just a component that wraps the full HTML document:

```html+jinja
{#def title='', description='', lang='en' #}

<!DOCTYPE html>
<html lang="{{ lang }}">
<head>
  <meta charset="utf-8">
  <title>{{ title }}</title>
  <meta name="description" content="{{ description }}">
  {{ assets.render_css() }}
</head>
<body {{ attrs.render() }}>
  {{ content }}
  {{ assets.render_js() }}
</body>
</html>
```

### Layout with Slots

Use named slots for customizable layout sections:

```html+jinja
{#def title='', lang='en' #}

<!DOCTYPE html>
<html lang="{{ lang }}">
<head>
  <meta charset="utf-8">
  <title>{{ title }}</title>
  {{ assets.render_css() }}
  {% slot head %}{% endslot %}
</head>
<body {{ attrs.render() }}>
  {% slot header %}
    <header><h1>{{ title }}</h1></header>
  {% endslot %}

  <main>{{ content }}</main>

  {% slot footer %}
    <footer>&copy; 2025</footer>
  {% endslot %}

  {{ assets.render_js() }}
  {% slot scripts %}{% endslot %}
</body>
</html>
```

Pages can override any slot:

```html+jinja
{#import "layouts/app.jx" as Layout #}

<Layout title="Dashboard">
  {% fill scripts %}
    <script src="{{ url_for('assets', file='js/dashboard.js') }}" type="module"></script>
  {% endfill %}

  <h2>Welcome back</h2>
</Layout>
```

### Nested Layouts

Compose layouts by wrapping one inside another:

```html+jinja
{#import "layouts/base.jx" as Base #}
{#import "sidebar.jx" as Sidebar #}
{#def title='' #}

<Base title={{ title }}>
  <div class="app-layout">
    <Sidebar />
    <main>{{ content }}</main>
  </div>
</Base>
```

### Navigation Highlighting

Pass the current page to the layout for active link styling:

```html+jinja
{#def current_page="" #}

<nav>
  <a href="/" class="{{ 'active' if current_page == 'home' else '' }}">Home</a>
  <a href="/about" class="{{ 'active' if current_page == 'about' else '' }}">About</a>
</nav>
```

In Proper, you can use `url_is()` and `url_startswith()` instead — they are available as template globals. The full list of Proper-registered globals is `current`, `url_for`, `url_is`, `url_startswith`, and `render_importmap` (used in the main layout to emit the `<script type="importmap">` tag). The `assets` global is auto-injected by Jx itself.

### Conditional Layout Sections

Use boolean props to toggle layout sections:

```html+jinja
{#def title='', show_sidebar=true, show_footer=true #}

<div class="layout">
  {% if show_sidebar %}
    <Sidebar />
  {% endif %}
  <main>{{ content }}</main>
  {% if show_footer %}
    <Footer />
  {% endif %}
</div>
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


## Working with htmx

Jx's underscore-to-dash attribute conversion makes htmx attributes natural:

```html+jinja
<Button hx_get="/api/items" hx_target="#list" hx_swap="innerHTML" />
```

Renders as `hx-get="/api/items" hx-target="#list" hx-swap="innerHTML"`.

### htmx Button Component

```html+jinja
{#def url, method="get", target="", swap="innerHTML", confirm="" #}

{% set hx_attr = "hx_" ~ method %}
{% do attrs.set(**{hx_attr: url}) %}
{% if target %}{% do attrs.set(hx_target=target) %}{% endif %}
{% do attrs.set(hx_swap=swap) %}
{% if confirm %}{% do attrs.set(hx_confirm=confirm) %}{% endif %}

<button {{ attrs.render(type="button", class="btn") }}>
  {{ content }}
</button>
```

### Loading States

```html+jinja
{#css loading-btn.css #}
{#def url #}

<button {{ attrs.render(class="btn") }} hx-get="{{ url }}">
  <span class="btn-text">{{ content }}</span>
  <span class="btn-loading">Loading...</span>
</button>
```

```css
.btn .btn-loading { display: none; }
.btn.htmx-request .btn-text { display: none; }
.btn.htmx-request .btn-loading { display: inline; }
```

### Search with Debounce

```html+jinja
<input type="search" name="q"
  hx-get="/search"
  hx-trigger="input changed delay:300ms, search"
  hx-target="#results"
  hx-indicator="#spinner"
/>
<span id="spinner" class="htmx-indicator">Searching...</span>
<div id="results"></div>
```

### Infinite Scroll

```html+jinja
{#def next_page #}

<div hx-get="{{ next_page }}"
     hx-trigger="revealed"
     hx-swap="outerHTML">
  Loading more...
</div>
```


## Catalog API

In a Proper app the catalog is `app.catalog`, already set up: the `views/` folder is registered, the modules are compiled to `COMPILED_PATH` (`_compiled/views/`) at startup, and the template globals, filters and tags are added. It is a `minijx.Catalog`.

### In Proper

```python
# More globals, filters or tests (e.g., from a tool's setup)
app.catalog.globals["site_name"] = "Acme"
app.catalog.add_filters({"money": format_money})
app.catalog.add_tests({"admin": lambda user: user.is_admin})

# Block tags: {% name args %}body{% endname %} calls function(args, caller=..., template=...)
# config: TEMPLATE_TAGS = {"card_box": card_box}
def card_box(title, *, caller, template):
    return Markup(f'<section class="box"><h2>{escape(title)}</h2>{caller()}</section>')
```

`caller()` renders the body only if the function calls it; `template` is the path of the component the tag is in. What the function returns is not escaped.

### Constructor

```python
from minijx import Catalog

Catalog(
    folder=None,            # Optional initial component folder
    *,
    auto_reload=True,       # Check the .jx files on every render (off in production)
    compiler=None,          # The minijx binary: None = bundled; False = never compile
    filters=None,           # Custom filters {name: callable}
    tests=None,             # Custom tests {name: callable}
    autoescape=True,        # Extensions escaped: True = ("html", "jx", "xml"); False = none
    tags=None,              # Block tags {name: callable}
    output=None,            # Folder for the compiled modules (default: next to each .jx)
    **globals               # Global template variables (catalog.globals)
)
```

A module is checked the first time it is loaded, in any mode, and compiled again if it is missing or out of date. `catalog.compile()` compiles every folder and raises `CompileError` listing every error.

### Rendering

```python
# Render a component file
html = catalog.render("home.jx", title="Hello", user=current_user)

# With globals (available to imported components too)
html = catalog.render(
    "home.jx",
    globals={"request": request},
    title="Hello",
)

# Render from a string: compiled once to a temporary folder;
# its imports are looked for in the catalog's folders
html = catalog.render_string("{#def name #}<p>{{ name }}</p>", name="World")
```

**`render()` arguments:**

- `relpath` — path to the component relative to its folder
- `globals` — dict of variables available to this component and all its imports
- `**kwargs` — arguments passed to the component only (not to its imports)

It returns `Markup` for a component with autoescape, `str` otherwise. An error while rendering has a traceback that points to the `.jx` file, line and expression.

`catalog.has_component(relpath)` tells if a component exists.
