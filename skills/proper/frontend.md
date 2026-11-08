---
title: Frontend
description: Frontend conventions — the views folder, layouts (slots, nesting, navigation), component assets, import maps, Stimulus, flash messages
last_verified: 2026-11-07
sources:
  - blueprint/[[app_name]]/views
  - blueprint/assets
  - blueprint/[[app_name]]/config/import_map.tt.py
  - src/proper/helpers/html.py
---

# Frontend

Proper uses Jx components for templates (compiled to Python functions by Proper), and Turbo Drive for fast page-to-page navigation. Static assets are served with automatic fingerprinting for long-term caching.

## Table of Contents

- [Templates](#templates)
- [Layouts](#layouts)
- [Component Assets](#component-assets)
- [Import Maps](#import-maps)
- [Stimulus](#stimulus)
- [Turbo Drive](#turbo-drive)
- [Flash Messages](#flash-messages)


## Templates

Templates are Jx components — files with Jinja's syntax, explicit prop declarations and an HTML-like call syntax. Most Jinja syntax works (`if`, `for`, `set`, filters, tests, macros); `include`, `extends`, `block`, `with`, `call`, `autoescape`, block-form `set` and `namespace()` don't — components and layouts replace them. See [jx.md](jx.md).

### Directory structure

```
myapp/views/
├── layouts/
│   ├── base.jx         # HTML document: head, CSS, import map, scripts
│   ├── app.jx          # Main layout: wraps base.jx with <Nav /> and <Flashes />
│   └── email.jx        # Email layout
├── emails/             # Email templates
├── public/
│   ├── index.jx
│   ├── error.jx
│   └── not_found.jx
├── form.jx             # Reusable <Form> component
├── flashes.jx          # Flash messages
└── nav.jx              # Site navigation (empty placeholder)
```

Templates live in the `views/` folder. The catalog is configured automatically at startup with `auto_reload` enabled in debug mode; the compiled modules go to `_compiled/views/`. `url_for` is registered as a pure global: a call with the same literal arguments is computed once per call site and remembered while the app runs.

### Component basics

A component declares its props with a `{#def ... #}` comment and receives child content through `{{ content }}`:

```html+jinja {title="myapp/views/form.jx (trimmed: the real file also lowercases `method`, turns put/patch/delete into a post with a hidden `_method` input, and sets `enctype` and `novalidate`)"}
{#def action="", method="post", multipart=False, novalidate=True -#}

<form {{ attrs.render(method=method, action=action) }}>
  {{ content }}
</form>
```

Components are imported and invoked with an HTML-like tag syntax:

```html+jinja {title="myapp/views/public/index.jx"}
{#import "layouts/app.jx" as Layout #}

<Layout title="Hello world!">
  Hello world!
</Layout>
```

### Template globals

The Jx catalog exposes several globals in every template:

| Global | Description |
|------- |-------------|
| `current`           | Request-scoped context: `current.app`, `current.request`, `current.response`, `current.user`, `current.auth_session`, `current.locale`, `current.timezone`, `current.csrf_token` (the last when token-based CSRF is enabled). The four `user`/`auth_session`/`locale`/`timezone` always work and return `None` when not set. |
| `url_for()`         | Generate URLs for named routes                   |
| `url_is()`          | Check if the current URL matches a route         |
| `url_startswith()`  | Check if the current URL starts with a prefix    |
| `dom_id`            | Generate a stable id for an object, suitable for use in HTML element ids. |
| `stream`/`turbo_stream` | Generates a `<turbo-stream>` tag, See [turbo.md](turbo.md) |
| `frame`/`turbo_frame`   | Generates a `<turbo-frame>` tag, See [turbo.md](turbo.md) |
| `render_importmap()`| Renders the `<script type="importmap">` tag (see [Import Maps](#import-maps)) |
| `truncate`          | Shorten a string; also available as a filter |
| `_`, `format_date`, `format_currency`, `format_decimal`, ... | i18n and Babel formatting helpers, always registered (see [i18n.md](i18n.md)) |
| `assets`            | Asset collector, added by the view compiler to every top-level render: `collect_css()`, `collect_js()` (see [Component Assets](#component-assets)). Its `render_css()`/`render_js()` emit the declared paths as-is, without `url_for`, so in Proper use the `collect_*` loops |

`app` itself is **not** a template global — use `current.app` if you need it. Flash messages live on the request: `current.request.flashes` returns a list of `(type, message)` tuples.

### Implicit rendering

If a controller action returns `None`, Proper renders the inferred template at `views/{module}/{action}.jx`. You only need to call `self.render()` explicitly when the template name doesn't match the convention. See [rendering.md](rendering.md#implicit-template-rendering) for details.


## Layouts

The generated app has two layout files: `layouts/base.jx` is the HTML document (stylesheets, import map, scripts, component-declared assets), and `layouts/app.jx` imports it and adds `<Nav />` and `<Flashes />` around `{{ content }}`. Pages use `app.jx`. The general structure of `base.jx`:

```html+jinja {title="myapp/views/layouts/base.jx"}
<!DOCTYPE html>
<html lang="{{ lang }}">
<head>
  {# Basic meta tags #}
	{# Global CSS declarations #}
  {# CSS declared by Jx components #}
  {# Importmap #}
  {# Global JS declarations #}
  {# JS declared by Jx components #}
  {# More meta tags #}
</head>
<body>
  ...
</body>
</html>
```

The patterns below show how to build the layout component itself. The `assets` and `render_importmap()` calls it makes are in [Component Assets](#component-assets) and [Import Maps](#import-maps).

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
  {% for url in assets.collect_css() -%}
    <link rel="stylesheet" href="{{ url_for('assets', file=url) }}">
  {% endfor -%}
</head>
<body {{ attrs.render() }}>
  {{ content }}
  {% for url in assets.collect_js() -%}
    <script src="{{ url_for('assets', file=url) }}" type="module"></script>
  {% endfor -%}
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
  {% for url in assets.collect_css() -%}
    <link rel="stylesheet" href="{{ url_for('assets', file=url) }}">
  {% endfor -%}
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

  {% for url in assets.collect_js() -%}
    <script src="{{ url_for('assets', file=url) }}" type="module"></script>
  {% endfor -%}
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

In Proper, use `url_is()` and `url_startswith()` instead: they are template globals (see [the table above](#template-globals)).

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


## Component Assets

Jx components can declare their own CSS and JavaScript dependencies. The layout collects these at render time, so each component bundles its own assets without the layout needing to know about them.

In the layout, `assets.collect_css()` and `assets.collect_js()` return the paths declared by all components used on the current page:

```html+jinja {title="myapp/views/layouts/base.jx"}
{# CSS declared by Jx components #}
{% for url in assets.collect_css() -%}
  <link rel="stylesheet" href="{{ url_for('assets', file=url) }}">
{% endfor -%}

{# JS declared by Jx components #}
{% for url in assets.collect_js() -%}
  <script src="{{ url_for('assets', file=url) }}" type="module"></script>
{% endfor -%}
```

See [jx.md](jx.md) for details on declaring assets in components.


## Import Maps

Proper uses browser-native [import maps](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/script/type/importmap) to resolve bare module specifiers (like `@hotwired/stimulus`) without a bundler.

### Configuration

The `IMPORT_MAP` config dict maps package names to asset paths. Proper ships with defaults for Stimulus and Turbo:

```python {title="config/import_map.py"}
# Default (provided by the framework):
IMPORT_MAP = {
    "@hotwired/stimulus": "js/vendor/stimulus.js",
    "@hotwired/turbo": "js/vendor/turbo.js",
}

# Add your own entries:
IMPORT_MAP = {
    "@hotwired/stimulus": "js/vendor/stimulus.js",
    "@hotwired/turbo": "js/vendor/turbo.js",
    "alpinejs": "https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js",
}
```

**URL resolution:** Values starting with `http` (so `https` too) or `/` are output as-is (for CDN or absolute URLs). All other values are resolved through `url_for('assets', file=...)`, which adds fingerprinting for long-term caching.

The channels and rich_text addons append their own entries (`cable`, `lexxy`). Config dicts deep-merge, so `IMPORT_MAP = {}` does not remove the defaults.

### Usage in layouts

Call `{{ render_importmap() }}` in the layout **before** any `<script type="module">` tags:

```html+jinja
{{ render_importmap() }}
<script src="{{ url_for('assets', file='js/vendor/turbo.js') }}" type="module"></script>
<script src="{{ url_for('assets', file='js/app.js') }}" type="module"></script>
```

This renders `<script type="importmap" data-turbo-track="reload">` with the resolved URLs, so Turbo Drive reloads the page when the map changes. In `DEBUG`, when `CABLE_PORT` is set, it also emits `<meta name="cable-port" content="...">` for `cable.js`. Component JavaScript can then use bare imports:

```js
import { Controller } from "@hotwired/stimulus";
```


## Stimulus

The generated app bundles [Stimulus](https://stimulus.hotwired.dev) (`assets/js/vendor/stimulus.js`, resolved through the import map as `@hotwired/stimulus`). `assets/js/application.js` starts it and exposes the application as `window.Stimulus`. There is no controller autoloading: every controller file registers itself, and the Jx component that uses it declares the file with `{#js #}`.

Conventions:

- One controller per file at `assets/js/<identifier>-controller.js`, kebab-case identifier named after the behavior (`toggle`, `autosave`, `char-count`), not after the page.
- The file ends with `window.Stimulus.register("<identifier>", ControllerClass)`.
- The component that renders the markup declares `{#js "js/<identifier>-controller.js" #}` (paths relative to `assets/`; several files separated by commas; quotes optional). The layout emits each declared script once per page as `<script type="module">`, so the controller loads only where it is used.
- Pass data from Python with values (`data-<identifier>-<name>-value="{{ ... }}"`, `| tojson` for arrays and objects), and CSS class names with classes (`data-<identifier>-<name>-class="..."`). Keep hard-coded class names and URLs out of the controller.
- Through `attrs` or any keyword argument, underscores become dashes: `attrs.set(data_toggle_target="panel")` renders `data-toggle-target="panel"`.

```js {title="assets/js/toggle-controller.js"}
import { Controller } from "@hotwired/stimulus"

class ToggleController extends Controller {
  static targets = ["panel"]
  static classes = ["open"]

  toggle() {
    this.panelTarget.hidden = !this.panelTarget.hidden
    this.element.classList.toggle(this.openClass)
  }

  close() {
    this.panelTarget.hidden = true
    this.element.classList.remove(this.openClass)
  }

  closeOutside(event) {
    if (!this.element.contains(event.target)) this.close()
  }
}

window.Stimulus.register("toggle", ToggleController)
```

```html+jinja {title="myapp/views/disclosure.jx"}
{#js "js/toggle-controller.js" #}
{#def label #}

<div data-controller="toggle" data-toggle-open-class="is-open"
     data-action="keydown.esc->toggle#close click@window->toggle#closeOutside">
  <button type="button" data-action="toggle#toggle">{{ label }}</button>
  <div data-toggle-target="panel" hidden>{{ content }}</div>
</div>
```

Stimulus API in brief (full reference: https://stimulus.hotwired.dev/reference/controllers):

| Declaration | HTML attribute | In the controller |
|-------------|----------------|-------------------|
| `static targets = ["panel"]` | `data-<id>-target="panel"` | `this.panelTarget`, `this.panelTargets`, `this.hasPanelTarget`, `panelTargetConnected(el)` |
| actions | `data-action="event->id#method"` (`@window`, `.esc`, `:prevent`, `:stop`, `:once`) | `method(event)`; default event: `click` on buttons/links, `input` on fields, `change` on selects, `submit` on forms |
| `static values = { url: String, n: { type: Number, default: 1 } }` | `data-<id>-url-value="..."` | `this.urlValue`, `urlValueChanged(value, old)` |
| `static classes = ["open"]` | `data-<id>-open-class="is-open"` | `this.openClass`, `this.openClasses` |
| `static outlets = ["result"]` | `data-<id>-result-outlet=".selector"` | `this.resultOutlet`, `this.resultOutlets` |
| lifecycle | — | `initialize()`, `connect()`, `disconnect()` |
| events | `data-action="<id>:saved->other#method"` | `this.dispatch("saved", { detail })` |

With Turbo:

- Drive swaps the `<body>`, so `connect()` runs again on every visit and `disconnect()` on every departure. Anything `connect()` adds outside the element (window listeners, intervals, observers) must be removed in `disconnect()`.
- Module scripts already in `<head>` do not run again on a Drive visit; new ones are added and run once. `register` is therefore called once per controller per browser tab.
- The page snapshot for "Back" is taken **before** the body is swapped, so `disconnect()` cannot clean it. Listen for `turbo:before-cache` on `document` to reset state that should not be cached, or mark elements with `data-turbo-temporary`.
- Controllers inside a frame or stream fragment connect when the fragment is inserted; `<name>TargetConnected` fires for appended targets.

The addons ship real controllers to copy from: `show-password-controller.js` (auth), `file-input-controller.js` and `image-input-controller.js` (storage).


## Turbo Drive

The generated app loads [Turbo](https://turbo.hotwired.dev) from `assets/js/vendor/turbo.js`, so every same-origin link and form is a partial navigation with no custom JavaScript. Opt out of one with `data-turbo="false"`. Drive, Frames and Streams are in [turbo.md](turbo.md).


## Flash Messages

The generated `flashes.jx` component renders one-time flash messages set during a redirect (see [rendering.md](rendering.md#flash-messages)):

```html+jinja {title="myapp/views/flashes.jx"}
{% set flashes = current.request.flashes %}

{%- if flashes %}
<div class="alerts" aria-live="polite">
  {% for cat, msg in flashes -%}
  <div class="alert alert--{{ cat }}" role="alert">
    {{ msg | safe }}
  </div>
  {% endfor -%}
</div>
{%- endif %}
```

Flash categories (`cat`) are `"positive"` (the default of `redirect_to`), `"negative"`, `"warning"` or `"info"` by convention. Style each with a corresponding `.alert--{category}` CSS class.
