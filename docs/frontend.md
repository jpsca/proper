title: Frontend
----

# Frontend

Proper uses [Jx](https://jx.scaletti.dev) for component-based templates, Tailwind CSS for styling, and Turbo Drive for fast page-to-page navigation. Static assets are served with automatic fingerprinting for long-term caching.


```
myapp/
├── assets/
│   ├── styles/
│   │   ├── _input.css           # Tailwind input
│   │   └── styles.css           # Tailwind output (generated)
│   ├── javascript/
│   │   ├── app.js               # Main app JS
│   │   └── turbo.es2017-umd.js  # Turbo Drive library
│   └── favicon.ico
├── views/
│   ├── layouts/                 # Page layouts
│   ├── common/                  # Shared components (nav, flashes)
│   └── pages/                   # Page templates
└── router.py                    # Static route registration
```


## 1. Templates

Templates are [Jx](https://jx.scaletti.dev) components — Jinja2 files with explicit prop declarations and an HTML-like call syntax. All standard Jinja2 syntax still works; Jx adds a component layer on top.

### 1.1 Directory structure

```
myapp/views/
├── layouts/
│   ├── app.jinja          # Main HTML layout
│   └── email.jinja        # Email layout
├── common/
│   ├── nav.jinja          # Navigation bar
│   └── flashes.jinja      # Flash messages
├── pages/
│   └── public/
│       ├── index.jinja
│       ├── error.jinja
│       └── not_found.jinja
└── form.jinja             # Reusable form component
```

Templates live in the `views/` folder. The catalog is configured automatically at startup with `auto_reload` enabled in debug mode.

### 1.2 Component basics

A component declares its props with a `{#def ... #}` comment and receives child content through `{{ content }}`:

```html+jinja {title="myapp/views/form.jinja"}
{#def action="", method="post", multipart=False, novalidate=True -#}

<form {{ attrs.render(method=method, action=action) }}>
  {{ content }}
</form>
```

Components are imported and invoked with an HTML-like tag syntax:

```html+jinja {title="myapp/views/pages/public/index.jinja"}
{#import "layouts/app.jinja" as Layout #}

<Layout title="Hello world!">
  Hello world!
</Layout>
```

### 1.3 Template globals

The Jx catalog exposes several globals in every template:

| Global              | Description                                      |
|---------------------|--------------------------------------------------|
| `current`           | Request-scoped context with the current `request`, `app`, etc. |
| `url_for()`         | Generate URLs for named routes                   |
| `url_is()`          | Check if the current URL matches a route         |
| `url_startswith()`  | Check if the current URL starts with a prefix    |
| `assets`            | Jx asset collector (see section 4)               |

### 1.4 Implicit rendering

If a controller action returns `None`, Proper renders the inferred template at `pages/{module}/{action}.jinja`. You only need to call `self.render()` explicitly when the template name doesn't match the convention. See [Controllers](./controllers.md) for details.


## 2. Layouts

The main layout loads stylesheets, scripts, and any component-declared assets:

```html+jinja {title="myapp/views/layouts/app.jinja"}
{#def title = '', description='', lang='en' #}

<!DOCTYPE html>
<html lang="{{ lang }}">
<head>
  <link rel="stylesheet" href="{{ url_for('assets', file='styles/styles.css') }}">

  {# CSS declared by Jx components #}
  {% for url in assets.collect_css() -%}
    <link rel="stylesheet" href="{{ url_for('assets', file=url) }}">
  {% endfor -%}

  <script src="{{ url_for('assets', file='javascript/turbo.es2017-umd.js') }}" type="module"></script>
  <script src="{{ url_for('assets', file='javascript/app.js') }}" type="module"></script>

  {# JS declared by Jx components #}
  {% for url in assets.collect_js() -%}
    <script src="{{ url_for('assets', file=url) }}" type="module"></script>
  {% endfor -%}
</head>
<body {{ attrs.render() }}>
  <Nav />
  <Flashes />
  {{ content }}
</body>
</html>
```

`assets.collect_css()` and `assets.collect_js()` return the CSS and JavaScript files declared by any Jx component used in the page, so each component can bundle its own assets without the layout needing to know about them.


## 3. Tailwind CSS

Proper uses [Tailwind CSS v4](https://tailwindcss.com) for utility-first styling. During development, the Tailwind CLI watches for changes and rebuilds the output file automatically.

### 3.1 File layout

```
myapp/assets/styles/
├── _input.css     # Tailwind input — your custom CSS goes here
└── styles.css     # Generated output (do not edit manually)
```

The input file imports Tailwind and defines custom properties:

```css {title="myapp/assets/styles/_input.css"}
@import "tailwindcss";

:root {
  --accent: #3082f6;
  --accent-hover: #1266e2;
  --accent-fg: #f5f7ff;
  --error: var(--color-red-600);
  --disabled: var(--color-gray-200);
  --border-radius: 0.5rem;
}
```

### 3.2 Development workflow

When you run `proper run`, a custom CLI class starts the Tailwind watcher as a subprocess before booting the dev server:

```python {title="myapp/cli/app_cli.py"}
import subprocess
from ..main import app

class AppCLI(app.CLI):
    def run(self):
        subprocess.Popen([
            "tailwindcss",
            "-i", "myapp/assets/styles/_input.css",
            "-o", "myapp/assets/styles/styles.css",
            "--watch",
        ], process_group=0)
        super().run()
```

This means `proper run` is the only command you need — it starts both the web server and the Tailwind watcher. Install the standalone `tailwindcss` CLI binary for this to work.

### 3.3 Production builds

For production, run the Tailwind CLI once with minification:

```bash
tailwindcss -i myapp/assets/styles/_input.css -o myapp/assets/styles/styles.css --minify
```


## 4. Component Assets

Jx components can declare their own CSS and JavaScript dependencies. The layout collects these at render time, so each component bundles its own assets without the layout needing to know about them.

In the layout, `assets.collect_css()` and `assets.collect_js()` return the paths declared by all components used on the current page:

```html+jinja {title="myapp/views/layouts/app.jinja"}
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


## 5. Turbo Drive

The generated app includes [Turbo Drive](https://turbo.hotwired.dev/handbook/drive), which intercepts link clicks and form submissions to replace just the `<body>` without a full page reload. This gives your multi-page app a faster, SPA-like navigation feel with no custom JavaScript required.

The library is loaded from `assets/javascript/turbo.es2017-umd.js` in the layout:

```html+jinja
<script src="{{ url_for('assets', file='javascript/turbo.es2017-umd.js') }}" type="module"></script>
```

Turbo Drive works automatically once the script is loaded. All same-origin link clicks and form submissions are accelerated. To opt out for specific links or forms, add `data-turbo="false"`:

```html
<a href="/slow-page" data-turbo="false">Load without Turbo</a>
```


## 6. Flash Messages

The generated `common/flashes.jinja` component renders one-time flash messages set during a redirect (see [Controllers — Flash Messages](./controllers.md#61-flash-messages)):

```html+jinja {title="myapp/views/common/flashes.jinja"}
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
