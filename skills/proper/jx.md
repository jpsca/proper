---
title: Jx Components
description: Component template system — imports, props, slots, attrs, assets, htmx, Catalog API
last_verified: 2026-04-02
---

# Jx Components

Jx is a component-based template system built on Jinja2. Components are `.jx` files with explicit imports, prop declarations, and an HTML-like call syntax. All standard Jinja2 syntax works; Jx adds a component layer on top.

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
{#import "common/nav.jx" as Nav #}
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

### Prefixed Imports

For components from prefixed catalog folders. Use for third-party component libraries:

```python
catalog.add_folder("vendor/ui-lib", prefix="ui")
```

```html+jinja
{#import "@ui/button.jx" as Button #}
```

Components within a prefixed folder can also use relative imports to reference siblings.


## Arguments (Props)

### Declaring

Use `{#def ...#}` at the top of a component:

```html+jinja
{#def title, count=0, active=true, items=[] #}

<h2>{{ title }}: {{ count }}</h2>
```

- `title` — required (no default)
- `count` — optional (defaults to `0`)

Defaults can be any Python value: strings, numbers, booleans, lists, dicts, etc. The expression is evaluated once when the component is parsed and the resulting object is stored on the component. **At every render, Jx makes a shallow copy of the stored value** when it is a `list`, `dict`, or `set` — so `tags=[]` and `config={}` are not shared between renders. The shallow copy does not extend to nested mutables (a list inside a default dict is still shared) or to custom mutable classes; default to `None` and create the value in the body when those matter.

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

When the annotation resolves to a Python built-in (`int`, `str`, `bool`, `list`, `dict`, `tuple`, `set`, `float`, `bytes`), Jx runs `isinstance(value, expected_type)` at render time and raises `InvalidPropType` on a mismatch. Type checking is **shallow**: for `list[str]`, only the outer `list` is checked; the elements are not inspected. The same applies to `dict[str, int]`.

Annotations that don't resolve to a built-in — custom classes, unions like `int | str`, `Optional[int]`, `typing.Iterable[str]` — are silently ignored at runtime. They survive on the component signature for tooling but no `isinstance` check happens. Stick to built-ins for strict checking; drop the annotation when you need a permissive shape.

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
- **Absolute path**: `/assets/styles/global.css`
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
{#import "common/sidebar.jx" as Sidebar #}
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

In Proper, you can use `url_is()` and `url_startswith()` instead — they are available as template globals.

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

### Constructor

```python
Catalog(
    folder=None,            # Optional initial component folder
    *,
    jinja_env=None,         # Custom Jinja2 environment
    extensions=None,        # Extra Jinja2 extensions
    filters=None,           # Custom template filters {name: callable}
    tests=None,             # Custom template tests {name: callable}
    auto_reload=True,       # Auto-detect file changes (disable in prod)
    asset_resolver=None,    # Callable (url, prefix) -> resolved_url for package assets
    **globals               # Global template variables
)
```

The `jinja2.ext.do` extension is always enabled (required for `attrs` manipulation).

### Adding Folders

```python
catalog.add_folder(
    path,                   # Absolute path to component folder
    *,
    prefix="",              # Namespace prefix (use @prefix/ in imports)
    assets=None,            # Path to CSS/JS assets folder for this prefix
)
```

Multiple folders with the same prefix are treated as one namespace. If both contain a component with the same path, the first one added wins.

You cannot move or delete component files from a folder after calling `add_folder()`, but you can call it again to pick up new files.

### Adding Packages

```python
catalog.add_package("my_ui_kit", prefix="ui")
```

Registers components (and optionally assets) from an installed Python package. The package module must expose a `JX_COMPONENTS` attribute pointing to the components folder. It may also expose `JX_ASSETS` pointing to an assets folder.

### Collecting Package Assets

```python
catalog.collect_assets("static/vendor")
```

Copies all registered package assets to an output folder. For each prefix that has a registered assets folder, files are copied to `<output>/<prefix>/`. Returns a list of `(prefix, relative_path)` tuples for every file copied.

### Rendering

```python
# Render a component file
html = catalog.render("pages/home.jx", title="Hello", user=current_user)

# With globals (available to imported components too)
html = catalog.render(
    "pages/home.jx",
    globals={"request": request},
    title="Hello",
)

# Render from a string (not cached, no relative imports)
html = catalog.render_string("{#def name #}<p>{{ name }}</p>", name="World")
```

**`render()` arguments:**

- `relpath` — path to the component relative to its folder
- `globals` — dict of variables available to this component and all its imports
- `**kwargs` — arguments passed to the component only (not to its imports)

### Introspection

```python
# List all registered component paths
catalog.list_components()

# Get a component's signature (required/optional args, slots, assets)
catalog.get_signature("card.jx")
# => {
#   "required": {"title": <class 'str'>, "count": None},  # {name: type or None}
#   "optional": {"subtitle": ("", <class 'str'>)},         # {name: (default, type or None)}
#   "slots": ("header", "footer"),
#   "css": ("card.css",),
#   "js": ()
# }
```
