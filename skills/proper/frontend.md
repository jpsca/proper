---
title: Frontend
description: Frontend conventions — Jx components, layouts, Turbo Drive, static assets, flash messages
last_verified: 2026-04-02
---

# Frontend

Proper uses [Jx](https://jx.scaletti.dev) for component-based templates, and Turbo Drive for fast page-to-page navigation. Static assets are served with automatic fingerprinting for long-term caching.

## Table of Contents

- [Templates](#templates)
- [Layouts](#layouts)
- [Component Assets](#component-assets)
- [Import Maps](#import-maps)
- [Turbo Drive](#turbo-drive)
- [Flash Messages](#flash-messages)

## Templates

Templates are [Jx](https://jx.scaletti.dev) components — Jinja2 files with explicit prop declarations and an HTML-like call syntax. All standard Jinja2 syntax still works; Jx adds a component layer on top.

### Directory structure

```
myapp/views/
├── layouts/
│   ├── app.jx          # Main HTML layout
│   └── email.jx        # Email layout
├── public/
│   ├── index.jx
│   ├── error.jx
│   └── not_found.jx
├── form.jx             # Reusable <Form> component
├── flashes.jx          # Flash messages
└── nav.jx              # Site navigation
```

Templates live in the `views/` folder. The catalog is configured automatically at startup with `auto_reload` enabled in debug mode.

### Component basics

A component declares its props with a `{#def ... #}` comment and receives child content through `{{ content }}`:

```html+jinja {title="myapp/views/form.jx"}
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

| Global              | Provided by | Description                                      |
|---------------------|-------------|--------------------------------------------------|
| `current`           | Proper      | Request-scoped context: `current.app`, `current.request`, `current.response`, `current.user`, `current.auth_session`, `current.locale`, `current.timezone`, `current.csrf_token` (the last when token-based CSRF is enabled). The four `user`/`auth_session`/`locale`/`timezone` always work and return `None` when not set. |
| `url_for()`         | Proper      | Generate URLs for named routes                   |
| `url_is()`          | Proper      | Check if the current URL matches a route         |
| `url_startswith()`  | Proper      | Check if the current URL starts with a prefix    |
| `render_importmap()`| Proper      | Renders the `<script type="importmap">` tag      |
| `assets`            | Jx          | Asset collector with `render`, `render_css`, `render_js`, `collect_css`, `collect_js` (see section 4) |
| `_get_random_id`    | Jx          | Generate a unique HTML id (used internally; rarely called directly) |

`app` itself is **not** a template global — use `current.app` if you need it. Flash messages live on the request: `current.request.flashes` returns a list of `(type, message)` tuples.

### Implicit rendering

If a controller action returns `None`, Proper renders the inferred template at `views/{module}/{action}.jx`. You only need to call `self.render()` explicitly when the template name doesn't match the convention. See [Controllers](./controllers.md) for details.


## Layouts

The main layout loads stylesheets, scripts, and any component-declared assets.

This is the general structure of the file:

```html+jinja {title="myapp/views/layouts/app.jx"}
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

## Component Assets

Jx components can declare their own CSS and JavaScript dependencies. The layout collects these at render time, so each component bundles its own assets without the layout needing to know about them.

In the layout, `assets.collect_css()` and `assets.collect_js()` return the paths declared by all components used on the current page:

```html+jinja {title="myapp/views/layouts/app.jx"}
{# CSS declared by Jx components #}
{% for url in assets.collect_css() -%}
  <link rel="stylesheet" href="{{ url_for('assets', file=url) }}">
{% endfor -%}

{# JS declared by Jx components #}
{% for url in assets.collect_js() -%}
  <script src="{{ url_for('assets', file=url) }}" type="module"></script>
{% endfor -%}
```

See the [Jx documentation](https://jx.scaletti.dev) for details on declaring assets in components.


## Import Maps

Proper uses browser-native [import maps](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/script/type/importmap) to resolve bare module specifiers (like `@hotwired/stimulus`) without a bundler.

### Configuration

The `IMPORT_MAP` config dict maps package names to asset paths. Proper ships with defaults for Stimulus and Turbo:

```python {title="config/main.py"}
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

**URL resolution:** Values starting with `http` or `/` are output as-is (for CDN or absolute URLs). All other values are resolved through `url_for('assets', file=...)`, which adds fingerprinting for long-term caching.

### Usage in layouts

Call `{{ render_importmap() }}` in the layout **before** any `<script type="module">` tags:

```html+jinja
{{ render_importmap() }}
<script src="{{ url_for('assets', file='js/vendor/turbo.js') }}" type="module"></script>
<script src="{{ url_for('assets', file='js/app.js') }}" type="module"></script>
```

This renders a `<script type="importmap">` tag with the resolved URLs. Component JavaScript can then use bare imports:

```js
import { Controller } from "@hotwired/stimulus";
```


## Turbo Drive

The generated app includes [Turbo Drive](https://turbo.hotwired.dev/handbook/drive), which intercepts link clicks and form submissions to replace just the `<body>` without a full page reload. This gives your multi-page app a faster, SPA-like navigation feel with no custom JavaScript required.

The library is loaded from `assets/js/vendor/turbo.js` in the layout:

```html+jinja
<script src="{{ url_for('assets', file='js/vendor/turbo.js') }}" type="module"></script>
```

Turbo Drive works automatically once the script is loaded. All same-origin link clicks and form submissions are accelerated. To opt out for specific links or forms, add `data-turbo="false"`:

```html
<a href="/slow-page" data-turbo="false">Load without Turbo</a>
```


## Flash Messages

The generated `flashes.jx` component renders one-time flash messages set during a redirect (see [Controllers — Flash Messages](./controllers.md#61-flash-messages)):

```html+jinja {title="myapp/views/flashes.jx"}
{% set flashes = current.request.flashes %}

{%- if flashes %}
<div class="container mx-auto my-1 text-center">
  {% for mtype, msg in flashes -%}
  <div class="alert alert--{{ mtype }}">
    <p>{{ msg | safe }}</p>
  </div>
  {% endfor -%}
</div>
{%- endif %}
```

Flash types (`mtype`) are typically `"info"`, `"success"`, `"warning"`, or `"error"`. Style each with a corresponding `.alert--{type}` CSS class.
