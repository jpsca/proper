---
title: Jx Catalog API
description: Reference: `app.catalog` (globals, filters, tests, block tags via TEMPLATE_TAGS), the `Catalog` constructor, `render()` and `render_string()`
last_verified: 2026-11-07
sources:
  - src/proper/views/catalog.py
---

# Jx Catalog API

Read this to extend the catalog (a filter, a block tag) or to render a component outside a controller. Writing components is in [jx.md](../jx.md).

## Catalog API

In a Proper app the catalog is `app.catalog`, already set up: the `views/` folder is registered, the modules are compiled to `COMPILED_PATH` (`_compiled/views/`) at startup (or before, with `proper jx compile`: outside of `DEBUG`, the views already compiled are not compiled again), and the template globals, filters and tags are added. It is a `proper.views.Catalog`.

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

`caller()` renders the body only if the function calls it; `template` is the path of the component the tag is in. What the function returns is escaped unless it is `Markup` (the body `caller()` returns is), so wrap the HTML you build in `Markup`.

### Constructor

```python
from proper.views import Catalog

Catalog(
    folder=None,            # Optional initial component folder
    *,
    auto_reload=True,       # Check the .jx files on every render (off in production)
    compiler=None,          # The compiler: None = jxc, built with Proper; False = never compile
    filters=None,           # Custom filters {name: callable}
    tests=None,             # Custom tests {name: callable}
    autoescape=True,        # Extensions escaped: True = ("html", "jx", "xml"); False = none
    tags=None,              # Block tags {name: callable}
    output=None,            # Folder for the compiled modules (default: next to each .jx)
    pure=(),                # Globals with the same result for the same arguments (Proper: url_for):
                            # a call is made once per arguments (str, int, None) and remembered
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
# its imports are looked for in the catalog's folders. The catalog keeps
# the last `catalog.max_strings` (256) sources compiled.
html = catalog.render_string("{#def name #}<p>{{ name }}</p>", name="World")
```

**`render()` arguments:**

- `relpath` — path to the component relative to its folder
- `globals` — dict of variables available to this component and all its imports
- `**kwargs` — arguments passed to the component only (not to its imports)

It returns `Markup` for a component with autoescape, `str` otherwise. An error while rendering has a traceback that points to the `.jx` file, line and expression.

`catalog.has_component(relpath)` tells if a component exists.
