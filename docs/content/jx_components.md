---
title: Jx Components and Layouts
description: |
  Jx components are the pieces of Python that produce the HTML your users see in the browser. This guide covers writing components with props, slots, and content; how layouts wrap your pages; how Proper picks which template to render; and how to break a page up into reusable parts.
number_headers: true
---

# Jx Components and Layouts

In this guide, you will learn how Proper turns Python objects into HTML pages, and how to write components that are small enough to reuse and big enough to do something useful.

- What Jx is and how it differs from plain Jinja2.
- How to write a component, declare its props and slots, and use it in another template.
- How HTML attributes flow through to the root element with the `attrs` system.
- How CSS and JS dependencies are declared per-component and collected by the layout.
- How Proper picks which template to render for an action, and how layouts wrap the result.
- The template globals Proper makes available to every page.

For the asset-delivery side - filename fingerprinting, cache headers, the `router.static()` route, import maps - see the [Static Assets guide](/docs/assets).

---

## Introduction

Jx is a Python component library. A component is a `.jx` file: a small piece of HTML with a header that declares its arguments and dependencies. Components import each other and compose into pages. The output is plain HTML.

If you've used Django or Flask templates, the syntax in the body will feel familiar - Jx uses Jinja2 underneath, so `{% if %}`, `{% for %}`, `{{ value }}`, filters, and tests all work. The new bits are the header (a few `{# ... #}` directives at the top of the file) and the way components are *invoked* (as HTML tags, not via `{% include %}`).

Here's the smallest useful Jx component:

```html+jinja
{# myapp/views/components/card.jx #}
{#def title #}

<article class="Card">
  <h3>{{ title }}</h3>
  <div class="Card-body">{{ content }}</div>
</article>
```

And here's a page that uses it:

```html+jinja
{# myapp/views/home/show.jx #}
{#import "components/card.jx" as Card #}

<Card title="Welcome">
  Glad you're here.
</Card>
```

The page produces:

```html
<article class="Card">
  <h3>Welcome</h3>
  <div class="Card-body">Glad you're here.</div>
</article>
```

Two things to notice. First, the component is invoked as `<Card>` rather than `{% include %}` or `{{ card() }}` - Jx's parser recognizes capitalized tag names and treats them as components. Second, `{{ content }}` inside the component renders whatever was between the open and close tags - the same idea as a slot in Vue or `{% block %}` in Django, but driven by tag nesting rather than inheritance.

The rest of this guide covers the pieces you'll reach for past this minimum: declaring multiple props with defaults, named slots, attribute forwarding, CSS and JS dependencies, and the layouts and rendering conventions Proper layers on top.

:::note Jx
This guide aims to cover everything most Proper apps will need. For Jx internals not covered here (extending the catalog, the asset resolver, programmatic introspection), see the [Jx documentation](https://jx.scaletti.dev/){target="_blank"}.
:::

---

## Where Templates Live

A new application starts with this layout under `myapp/views/`:

```
views/
├── layouts/
│   ├── base.jx              # bare HTML shell (head, body, assets)
│   └── app.jx               # layout used by pages (base + nav + flashes)
├── public/
│   ├── index.jx
│   └── error.jx
├── card/
│   ├── index.jx
│   ├── show.jx
│   ├── new.jx
│   ├── edit.jx
│   └── form.jx
├── emails/                  # email-only templates
├── form.jx                  # framework <Form> component
├── flashes.jx           # flash message list
└── nav.jx               # site navigation
```

The convention is one folder per "kind" of template:

- **`<controller>/`** - one folder per controller. Each file matches an action (`index.jx`, `show.jx`, `new.jx`, `edit.jx`). The resource generator creates these for you.
- **`layouts/`** - the layouts pages wrap themselves in. Two by default; you can add more.
- **Top-level `.jx` files** (`nav.jx`, `flashes.jx`, `form.jx`, …) - components shared across the whole app: anything reused on most pages.
- **`emails/`** - templates rendered by mailers, not by HTTP requests.
- **Anywhere else** - feel free to add subdirectories like `components/`, `forms/`, `widgets/` for organizing your own components.

File names are **lowercase, snake_case, with the `.jx` extension**: `card.jx`, `nav_item.jx`, `pricing_table.jx`. The component is *invoked* with the PascalCase name (`<Card>`, `<NavItem>`, `<PricingTable>`) - Jx converts between the two.

:::note | What about `.html`?
Jx files use `.jx` rather than `.html` so editors and bundlers don't try to format them as HTML. The body is HTML; the header is not. Treating the whole file as plain HTML usually breaks the directives at the top.
:::

:::tip | Jx syntax extension
If you are using VisualStudio Code, install the [Jinja-Jx extension](https://github.com/jpsca/jx-vscode){target="_blank"} to get syntax highlighting, go-to-definition, and syntax validation.
:::

Proper sets up the catalog at startup with `myapp/views/` registered as the root folder. You don't manage the catalog manually - it just exists, and any `.jx` file under `views/` is reachable.

---

## Anatomy of a Component

A complete component, with every directive used at least once:

```html+jinja
{# myapp/views/components/card.jx #}
{#import "icons/star.jx" as Star #}
{#css "card.css" #}
{#js "card.js" #}
{#def title, badge=None, size="md" #}

<article class="Card Card-{{ size }}" {{ attrs.render() }}>
  <h3 class="Card-title">
    {{ title }}
    {% if badge %}<Star /> <span class="Card-badge">{{ badge }}</span>{% endif %}
  </h3>
  <div class="Card-body">
    {{ content }}
  </div>
</article>
```

The first lines are the **header**: zero or more directives wrapped in `{# ... #}`. After the header comes the **body**: regular Jinja2.

### The Header Directives

| Directive  | What it declares                                                  |
| ---------- | ----------------------------------------------------------------- |
| `#import`  | Another component this one uses, available as a tag in the body.  |
| `#def`     | The arguments (props) this component accepts.                     |
| `#css`     | A CSS file the component depends on.                              |
| `#js`      | A JavaScript file the component depends on.                       |

The order doesn't matter; each directive can appear multiple times; you can omit any of them. A component with only `#def` is fine. A component with no directives at all is fine too - it's just inert HTML.

Each directive lives on its own line, but you can pack arguments onto one line:

```html+jinja
{#import "icons/star.jx" as Star, "icons/warning.jx" as Warning #}
{#css "card.css", "card-anim.css" #}
{#js "card.js" #}
```

Comma-separated values go inside one directive; each directive type repeats only when you'd rather split for readability.

### The Body

After the header, the body is Jinja2. Everything you know works:

- `{{ expression }}` - render a value.
- `{% if %}`, `{% for %}`, `{% set %}`, `{% with %}` - control flow.
- `{% include %}`, `{% extends %}`, `{% block %}` - if you want them, though Jx components usually replace the `extends`/`block` pattern.
- Filters (`{{ name | upper }}`), tests (`{% if x is none %}`), macros (`{% macro foo() %}`).

Two implicit variables come for free in every component:

- **`content`** - whatever was between the component's opening and closing tags (covered in [Content and Slots](#content-and-slots)).
- **`attrs`** - any HTML attribute passed at the call site that wasn't declared in `#def` (covered in [`attrs`: HTML Attribute Forwarding](#attrs-html-attribute-forwarding)).

### What Jx Does Not Do

A few HTML-shaped things you might expect that Jx leaves alone:

- **No CSS scoping.** A component named `Card` doesn't get its CSS auto-scoped to itself; you write your selectors yourself ([CSS Scoping Conventions](#css-scoping-conventions) covers conventions).
- **No automatic prop validation by type.** `#def title` accepts anything truthy; `#def title: str` is valid syntax but the type is informational, not enforced at render time. Required vs optional *is* enforced (covered in [Props (Arguments)](#props-arguments)).
- **No client-side reactivity.** Jx is a server-side rendering library. To re-render parts of a page in the browser, pair Jx with htmx or Turbo Frames - both work because the component output is plain HTML.

---

## Using a Component

Three steps: import, invoke, optionally pass content.

### Import It

```html+jinja
{#import "components/card.jx" as Card #}
```

The path is relative to the catalog root (`myapp/views/`). The `as` name is what you'll use in the body - usually the PascalCase form of the file name, but anything that's a valid identifier works.

If the same component is imported with two different `as` names, both are valid; the one closer to the call site (later in the file) wins. There's no name conflict because Jx scopes imports to the file that declared them.

### Invoke It

```html+jinja
<Card title="Welcome">
  Glad you're here.
</Card>
```

Or self-closing when there's no content:

```html+jinja
<Card title="Welcome" />
```

The opening tag's attributes are the component's arguments. String attributes work as written:

```html+jinja
<Card title="Welcome" />
```

Expressions (any Python value) go inside `{{ }}`:

```html+jinja
<Card title={{ user.name }} count={{ orders | length }} />
```

Booleans are short-form attributes (no value):

```html+jinja
<Card featured />
```

That last form is the same as `featured={{ True }}`.

### The PascalCase Convention

A component file is `lowercase_snake.jx`; the tag name is PascalCase. Two-word names follow the same rule:

```
file: nav_item.jx       → tag: <NavItem>
file: pricing_table.jx  → tag: <PricingTable>
file: app_layout.jx     → tag: <AppLayout>
```

This is how Jx's parser distinguishes a component invocation from a regular HTML tag (which is always lowercase). Mixing cases (`<navItem>`, `<Pricing-Table>`) won't work.

---

## Imports

The `#import` directive accepts three path forms.

### Absolute

Absolute paths resolve from the catalog root (`myapp/views/`):

```html+jinja
{#import "components/card.jx" as Card #}
{#import "icons/star.jx" as Star #}
{#import "nav.jx" as Nav #}
```

This is the form you'll use most often. It works regardless of where the importing file lives.

### Relative

Relative paths start with `./` or `../` and resolve against the *current file's* directory:

```html+jinja
{# inside myapp/views/card/edit.jx #}
{#import "./form.jx" as Form #}
```

`./form.jx` is `myapp/views/card/form.jx` - the form partial that lives next to the edit page.

```html+jinja
{# inside myapp/views/admin/post/edit.jx #}
{#import "../../layouts/admin.jx" as Layout #}
```

Relative imports are most useful for components that travel together - a page and its dedicated form partial, a layout and a layout-only sub-component. For everything else, absolute imports are clearer.

### Prefixed

Prefixed imports use a colon to distinguish a registered "package" of components from your own folder:

```html+jinja
{#import "ui:button.jx" as Button #}
```

This form is rare in plain Proper apps - the default catalog has just one folder, registered without a prefix. Prefixes show up when an addon (or a third-party package) registers its own component folder. The `auth` blueprint, for example, can register its components under an `auth:` prefix to avoid colliding with your own.

You'll know you need this when an addon's documentation tells you to write `{#import "addon-name:component.jx" as Foo #}`. Until then, stick to absolute and relative imports.

---

## Props (Arguments)

`#def` declares the arguments a component accepts:

```html+jinja
{#def title, count=0, status="active" #}
```

That declares three arguments:

- `title` - **required**. Calling the component without it raises an error.
- `count` - **optional**, defaults to `0`.
- `status` - **optional**, defaults to `"active"`.

The order matters only for callers using positional arguments (which is rare); name your arguments at the call site and you can declare them in any order in `#def`.

### Required vs Optional

Any argument with a default is optional. Any argument without one is required. Forgetting a required argument raises a clear error at render time:

```
TypeError: Card() missing required argument: 'title'
```

To make an argument optional with no sensible default, default it to `None` and check in the body:

```html+jinja
{#def title, badge=None #}

<article>
  <h3>{{ title }}</h3>
  {% if badge %}<span class="badge">{{ badge }}</span>{% endif %}
</article>
```

### Default Values

Defaults can be any Python literal:

```html+jinja
{#def
    title,
    size="md",
    closeable=True,
    tags=[],
    config={"key": "value"}
#}
```

Multi-line `#def` is fine - Jx joins everything between `{#def` and `#}`. Use it to keep long argument lists readable.

:::note | Mutable defaults are safe (mostly)
Unlike Python function defaults, Jx makes a shallow copy of `list`, `dict`, and `set` defaults at every render - so `tags=[]` and `config={}` are not shared between calls. The exceptions are deeper structures (a list inside a default dict shares the inner list) and custom mutable classes (which aren't copied). For these, default to `None` and build the value in the body, just like in Python.
:::

### Type Hints

Type hints are accepted in `#def`:

```html+jinja
{#def title: str, count: int = 0 #}
```

When the annotation is a built-in Python type (`int`, `str`, `bool`, `list`, `dict`, `tuple`, `set`, `float`, `bytes`), Jx enforces it at render time with `isinstance`. Pass `count="abc"` to a component declared as `count: int = 0` and the render fails with `InvalidPropType` before the body runs.

For parameterized generics (`items: list[str]`), only the outer type is checked - Jx confirms the value is a `list`, but doesn't inspect the elements.

For anything else - your own classes, unions like `int | str`, `Optional[int]`, types from the `typing` module - the annotation is silently ignored at runtime. It still shows up in the component's signature for tooling and editor support, but no `isinstance` check happens.

If you want strict checking, stick to built-in types in `#def`. If you need to accept "an int or `None`", drop the annotation and validate in the body.

### Passing Arguments

At the call site, every value form is supported:

```html+jinja
{# Plain string #}
<Card title="Welcome" />

{# Expression: any Python value #}
<Card title={{ user.name }} count={{ orders | length }} />

{# Boolean shorthand: present means True #}
<Card featured />

{# Boolean negation, the long form #}
<Card featured={{ False }} />

{# String concat, formatting, and Jinja filters all work #}
<Card title="{{ user.name }}'s page" />
```

### Dash-to-Underscore Conversion

HTML attribute names use dashes (`data-user-id`, `aria-label`); Python identifiers use underscores. Jx maps between the two automatically:

```html+jinja
<Card data-user-id={{ user.id }} aria-label="A card" />
```

Inside the component, those become:

```html+jinja
{#def data_user_id, aria_label #}

<article data-user-id="{{ data_user_id }}" aria-label="{{ aria_label }}">
```

You write idiomatic HTML at the call site, idiomatic Python in the component body, and the conversion happens for you.

### Validation

When a component is rendered, Jx checks that every required prop was passed and that no unknown props were passed. The latter goes through the `attrs` system instead of erroring (next section).

The signature of every component is also queryable through the catalog - useful for tooling and tests:

```python
sig = app.catalog.get_signature("components/card.jx")
sig.required   # {"title": str}
sig.optional   # {"size": ("md", str), "badge": (None, ...)}
```

You won't reach for this often, but it's there.

---

## Content and Slots

Most components have one place where the parent puts arbitrary HTML: a card's body, a layout's main area, a button's label. That place is a **slot**, and the simplest version is the implicit `content` slot.

### The Implicit `content` Slot

Whatever appears between the opening and closing tags of a component lands in the `content` variable:

```html+jinja
{# component: card.jx #}
{#def title #}

<article class="Card">
  <h3>{{ title }}</h3>
  <div class="Card-body">{{ content }}</div>
</article>

{# call site #}
<Card title="Welcome">
  Glad you're <strong>here</strong>.
</Card>
```

`content` is the rendered HTML of everything between the tags. It's always available in the component's body; you don't need to declare it in `#def`.

For self-closing tags, `content` is empty - check it before rendering:

```html+jinja
<article>
  <h3>{{ title }}</h3>
  {% if content %}
    <div class="Card-body">{{ content }}</div>
  {% endif %}
</article>
```

### Fallback Content

A common pattern is "if the parent didn't pass anything, show this default":

```html+jinja
{#def title #}

<article>
  <h3>{{ title }}</h3>
  <div class="Card-body">
    {% if content %}
      {{ content }}
    {% else %}
      <em>No description.</em>
    {% endif %}
  </div>
</article>
```

The check is `{% if content %}` - empty content is falsy, so the fallback runs whenever the component is self-closing or has whitespace-only inner HTML.

### Named Slots

When one slot isn't enough - a card with a header and a footer, a modal with three regions - declare named slots in the component body with `{% slot name %}...{% endslot %}` and fill them at the call site with `{% fill name %}...{% endfill %}`:

```html+jinja
{# component: modal.jx #}
{#def title #}

<div class="Modal" role="dialog">
  <header class="Modal-header">
    <h2>{{ title }}</h2>
    {% slot controls %}{% endslot %}
  </header>
  <div class="Modal-body">{{ content }}</div>
  <footer class="Modal-footer">
    {% slot actions %}{% endslot %}
  </footer>
</div>
```

```html+jinja
{# call site #}
<Modal title="Confirm">
  {% fill controls %}
    <button aria-label="Close">×</button>
  {% endfill %}

  Are you sure you want to delete this card?

  {% fill actions %}
    <button>Cancel</button>
    <button class="danger">Delete</button>
  {% endfill %}
</Modal>
```

A few rules:

- The component's `{% slot name %}` block renders whatever the caller wrote inside the matching `{% fill name %}`.
- Anything *not* inside a `{% fill %}` block goes into the implicit `content` slot.
- A slot can declare default content between `{% slot %}` and `{% endslot %}`; that content renders when the caller doesn't supply a fill.

### Slots vs Props

Both pass data into a component. The line between them is roughly:

| Use a **prop** for...                       | Use a **slot** for...                              |
| ------------------------------------------- | -------------------------------------------------- |
| A short string or a Python value             | HTML markup, possibly with its own components      |
| Something the component formats             | Something the parent supplies as-is                |
| A boolean or a number                        | Anything that can vary in length and structure     |
| A configuration switch                       | A region the component leaves to the caller        |

A button's *label* is a prop until you need an icon next to the text - then it's a slot. A modal's *title* stays a prop because it's always one short string.

When in doubt, start with a prop. Convert to a slot when you find yourself wishing the prop could contain markup.

---

## Attrs: HTML Attribute Forwarding

A component is meant to be used like an HTML element. Real HTML elements accept arbitrary attributes - `id`, `class`, `data-*`, `aria-*`, `style`, `onclick`, plus everything specific to that element (`href` on `<a>`, `disabled` on `<button>`). You don't want to declare every possible attribute in `#def`; you want them to "pass through" to the right element in the component's output.

That's what `attrs` is for. Anything passed at the call site that *wasn't* declared in `#def` lands in `attrs`, and the component decides where to put it.

### The Problem It Solves

Without `attrs`, a `<Button>` component that accepts only `label` couldn't be styled with `class="primary"` or wired to JavaScript with `onclick=...` without declaring every possible attribute. Ten props per component, half of them just to forward to a `<button>`, gets old fast.

With `attrs`:

```html+jinja
{# component: button.jx #}
{#def label #}

<button {{ attrs.render() }}>{{ label }}</button>
```

```html+jinja
{# call site #}
<Button label="Save" id="save-button" class="primary" data-action="submit" />
```

Output:

```html
<button id="save-button" class="primary" data-action="submit">Save</button>
```

Every attribute that wasn't `label` flowed through to the `<button>` tag.

### `attrs.render()`

The simplest usage. `{{ attrs.render() }}` writes every collected attribute as an HTML attribute on whatever element it's placed on:

```html+jinja
<article {{ attrs.render() }}>
```

Boolean attributes are handled correctly - `disabled={{ True }}` renders as `disabled`, `disabled={{ False }}` renders as nothing, and `class="primary"` renders verbatim.

### Adding Defaults

Pass keyword arguments to `attrs.render()` to add defaults that the caller can override:

```html+jinja
<button {{ attrs.render(type="button", role="button") }}>
```

If the caller passed `type="submit"`, the output uses `type="submit"` (the call-site value wins). If the caller passed nothing, the output uses `type="button"`.

This is a *setdefault* semantic - you're saying "use this if the caller didn't provide one." For attributes that should always have a specific value regardless of the caller, see `attrs.set()` below.

### Class Merging

Classes are special. The caller often wants to *add* a class, not replace one:

```html+jinja
<button {{ attrs.render(class_="Button") }}>
```

```html+jinja
<Button class="danger" />
```

Output:

```html
<button class="Button danger">
```

Both classes appear. The component's `Button` class is preserved, and the caller's `danger` is appended.

The trailing-underscore on `class_` is because `class` is a Python reserved word. Jx strips the underscore when emitting HTML.

### The Methods on `attrs`

Beyond `render()`, `attrs` exposes a small API for finer control:

| Method                             | What it does                                                        |
| ---------------------------------- | ------------------------------------------------------------------- |
| `attrs.set(**kw)`                  | Set or replace attributes. Caller's value is **overridden**.        |
| `attrs.setdefault(**kw)`           | Set attributes only if not already present. Caller's value wins.    |
| `attrs.get(name, default=None)`    | Read an attribute's value (and remove it from `attrs`).             |
| `attrs.add_class(*classes)`        | Append one or more classes.                                         |
| `attrs.prepend_class(*classes)`    | Prepend one or more classes.                                        |
| `attrs.remove_class(*classes)`     | Remove one or more classes.                                         |
| `attrs.classes`                    | List of classes currently on `attrs`.                               |
| `attrs.as_dict`                    | Dict of every attribute on `attrs`.                                 |

Use these when you need to do something more than render-with-defaults. For example, *forcing* a `role="status"` on an alert no matter what the caller passed:

```html+jinja
{% do attrs.set(role="status") %}
<div {{ attrs.render(class_="Alert") }}>
  {{ content }}
</div>
```

The `{% do ... %}` tag is from `jinja2.ext.do`, enabled by default in Jx. It runs an expression for its side effect without rendering anything.

### Underscore-to-Dash Conversion

Just like props, `attrs` converts underscores to dashes when emitting HTML. So at the call site you write:

```html+jinja
<Card data-user-id={{ user.id }} aria-label="My card" />
```

And the component, if it inspects:

```html+jinja
{{ attrs.get("data_user_id") }}
{{ attrs.get("aria_label") }}
```

The underscore form is the Python identifier; the dash form is what shows up in the rendered HTML. You don't have to think about it - just use whichever feels natural in the context you're in.

### Three Worked Examples

**Button.** Add `type="button"` as a default, default class `Button`, merge any caller classes:

```html+jinja
{#def label #}

<button {{ attrs.render(type="button", class_="Button") }}>
  {{ label }}
</button>
```

```html+jinja
<Button label="Save" />
{# → <button type="button" class="Button">Save</button> #}

<Button label="Delete" class="danger" />
{# → <button type="button" class="Button danger">Delete</button> #}

<Button label="Submit" type="submit" />
{# → <button type="submit" class="Button">Submit</button> #}
```

**Card.** Default classes, but also force a `role="article"` for accessibility:

```html+jinja
{#def title #}

{% do attrs.set(role="article") %}

<article {{ attrs.render(class_="Card") }}>
  <h3>{{ title }}</h3>
  {{ content }}
</article>
```

`role` is `set`, not `setdefault`, so the caller can't override it.

**Input.** Read an attribute out before rendering, and use it to derive other things:

```html+jinja
{#def name, label #}

{% set field_id = attrs.get("id") or "field-" + name %}

<div class="Field">
  <label for="{{ field_id }}">{{ label }}</label>
  <input
    name="{{ name }}"
    id="{{ field_id }}"
    {{ attrs.render(type="text") }}
  />
</div>
```

`attrs.get("id")` reads the `id` attribute and removes it from `attrs` (so it doesn't get rendered twice). `attrs.render()` then writes everything that's left, plus the default `type="text"`.

### Forwarding Attrs to a Child Component

Sometimes a component is mostly a wrapper around another. The wrapper wants to forward whatever the caller passed straight through:

```html+jinja
{# component: link_button.jx #}
{#import "components/button.jx" as Button #}
{#def href, label #}

<a href="{{ href }}">
  <Button label={{ label }} attrs={{ attrs }} />
</a>
```

Passing `attrs={{ attrs }}` hands the full collected attribute bag to the child component, which can use `attrs.render()` exactly as if the caller had passed those attributes directly.

The application's own `app.jx` layout uses this pattern to forward attrs down to `base.jx`:

```html+jinja
{#import "nav.jx" as Nav #}
{#import "flashes.jx" as Flashes #}
{#import "./base.jx" as Layout #}

<Layout attrs={{ attrs }}>
  <Nav />
  <Flashes />
  {{ content }}
</Layout>
```

A page that does `<Layout class="dashboard">` ends up with `class="dashboard"` on the `<body>` tag in `base.jx`, two levels of wrapping later.

---

## Component Assets

A component often needs styles or scripts to look and behave right. Jx lets you declare those dependencies at the top of the component, and the layout collects them across the whole rendered page and emits the right `<link>` and `<script>` tags. No global stylesheet, no manual list of imports per page.

### Declaring Assets

`#css` and `#js` directives in the header:

```html+jinja
{#css "card.css", "card-anim.css" #}
{#js "card.js" #}
{#def title #}

<article class="Card">
  <h3>{{ title }}</h3>
  {{ content }}
</article>
```

Multiple files are comma-separated. Both directives can repeat for readability:

```html+jinja
{#css "card.css" #}
{#css "card-anim.css" #}
{#js "card.js" #}
```

Asset paths can be:

- **Relative to the assets folder** (`"card.css"`) - resolved through `url_for("assets", file="card.css")`, which means they get fingerprinted and cached aggressively (covered in the [Static Assets guide](/docs/assets)).
- **Absolute paths** (`"/vendor/foo.css"`) - used verbatim, no fingerprinting.
- **Full URLs** (`"https://cdn.example.com/lib.js"`) - used verbatim, no fingerprinting.

Use the relative form for assets that live in `myapp/assets/`. Use the absolute or URL form for things outside that tree.

### The `assets` Global

In any layout (or anywhere you want), call methods on the `assets` global to emit the collected dependencies:

```html+jinja
<head>
  {{ assets.render_css() }}
  {{ assets.render_js() }}
</head>
```

`assets.render_css()` emits a `<link rel="stylesheet">` for every CSS file declared by every component used on the page. `assets.render_js()` emits a `<script type="module">` for every JS file. `assets.render()` does both.

`render_js()` accepts two arguments:

```html+jinja
{{ assets.render_js() }}                              {# <script type="module" src="..."> #}
{{ assets.render_js(module=False) }}                  {# <script src="..." defer> #}
{{ assets.render_js(module=False, defer=False) }}     {# <script src="..."> #}
```

`module=True` (the default) is right for ES modules - the import map machinery only works with module scripts.

### The Collection Methods

If you want the URLs themselves rather than ready-made tags - to build a custom `<link>` or pass to a service worker manifest - use the collection methods:

```html+jinja
{% for url in assets.collect_css() -%}
  <link rel="stylesheet" href="{{ url_for('assets', file=url) }}">
{% endfor -%}

{% for url in assets.collect_js() -%}
  <script src="{{ url_for('assets', file=url) }}" type="module"></script>
{% endfor -%}
```

This is what the generated `base.jx` does. The result is the same as `render_css()` / `render_js()` but you control the surrounding markup.

### CSS Scoping Conventions

Jx does not scope CSS automatically. A `Card.jx` declaring `card.css` does not get its CSS limited to the rendered card - the rules in `card.css` apply to the whole page just like any other stylesheet.

The convention is to name your top-level class after the component and write all selectors as descendants of it:

```css
.Card {
  padding: 1rem;
  border: 1px solid #ccc;
}

.Card-title {
  font-size: 1.25rem;
  font-weight: 600;
}

.Card-body {
  margin-top: 0.75rem;
}
```

Use BEM-style class names (`Block-element--modifier`) or CSS nesting if your build pipeline supports it - Jx is unopinionated about which.

The bad pattern:

```css
/* Affects every <h3> on the page, even ones outside the card */
h3 { font-size: 1.25rem; }
```

There's nothing in Jx stopping you, but unscoped element selectors are how cards-styled-by-blogs end up bleeding into the rest of the application.

### How Collection Works

When a page is rendered, Jx walks the component tree at render time:

1. The page is the top-level component. Its `#css` and `#js` declarations are collected.
2. Every component the page imports adds its declarations to the same set.
3. Every component *those* import adds theirs, recursively.
4. Duplicates are dropped (a component used three times only contributes its CSS once).
5. The result is a deduplicated list, ordered: the page first, then components in import order, then their imports, and so on.

`render_css()` and `render_js()` emit one tag per item in that list. Each component's CSS appears at most once in the final HTML, regardless of how many times the component was used.

The collection happens during rendering, so it picks up exactly the components used on *this* page - no manual asset manifest, no per-page tracking. A page that uses `<Card>` gets card.css; a page that doesn't, doesn't.

---

## Implicit Rendering: How Proper Picks a Template

When a controller action returns `None` and doesn't set a response body, Proper renders a template automatically. The template path comes from the controller's class hierarchy and the action name, and the file extension comes from the request's `Accept` header. The whole algorithm is in `proper/template_resolver.py` and isn't long, so this section walks through what happens for a typical request.

### The Pattern

For a request to `GET /cards/42` matching `CardController.show`, the action body is empty:

```python
@router.resource("cards")
class CardController(AppController):
    def show(self):
        pass        # what happens here?
```

Proper looks for a template at `card/show.jx`. If it exists, it's rendered with every instance attribute on the controller (e.g. `self.card`) available as a template variable.

The folder name comes from the controller class name (`CardController` → `card`), the file name from the action (`show` → `show.jx`).

### The Prefix Chain

Controllers often inherit from each other. The lookup walks the inheritance chain so a child controller can fall back to its parent's templates:

```python
class AdminController(AppController):
    def index(self):
        pass


class AdminPostController(AdminController):
    def index(self):
        pass
```

For `AdminPostController.index`, Proper looks at:

1. `admin_post/index.jx` (the child's own folder)
2. `admin/index.jx` (the parent's folder, if step 1 misses)

This keeps shared admin layouts in `admin/` instead of duplicating them under every admin sub-controller.

The chain stops at the framework's `Controller` base class - your `AppController` and any concerns are walked, but `proper.Controller` itself isn't.

### Format Negotiation

The request's `Accept` header decides the template's *format* part. For a request asking for `application/json`, the lookup tries:

1. `card/show.json.jx`
2. `card/show.jx` (fallback, no format extension)

For a normal browser request asking for `text/html`:

1. `card/show.html.jx`
2. `card/show.jx`

The `.html.jx` form is rare in practice - most apps just use `.jx` and let it serve HTML. The `.json.jx` form is the common one: a single controller can serve both HTML and JSON for the same action by having two templates side by side.

When the `Accept` header is `*/*` (or missing), the lookup uses the request's `default_format`, which is `"html"` unless you've changed it. So a cURL with no `-H 'Accept: ...'` lands in the HTML branch.

### The Full Algorithm

Combining all three: for `AdminPostController.index` with `Accept: application/json, */*`:

```
admin_post/index.json.jx     (step 1)
admin_post/index.jx          (step 2)
admin/index.json.jx          (step 3)
admin/index.jx               (step 4)
```

The first one that exists in the catalog wins. If none exist, Proper raises `ComponentNotFoundError` listing every candidate it tried - which is what you want when debugging a "I added a template but it's not picking it up" problem.

### When to Override

`self.render(name, ...)` skips the lookup and renders a specific template:

```python
def show(self):
    self.card = Card.get_or_none(self.params["card_id"])
    if not self.card:
        return self.render("card/not_found.jx", status=404)
```

The path is the catalog name, exactly as you'd write it in `#import`. No prefix walk, no format negotiation - just "render this file."

For JSON or text responses without a template, the [Controllers Overview](/docs/controllers#rendering-responses) covers `self.render(json=...)` and `self.render(text=...)`.

---

## Layouts

A layout is a component that wraps the page. The page calls it as a tag, the layout renders the surrounding HTML (head, nav, footer), and the page's own content goes in the slot.

The generator creates two layouts in `views/layouts/`:

- **`base.jx`** - the bare HTML document (head, body, asset collection, import map). This is the outer shell.
- **`app.jx`** - wraps `base.jx` and adds the navigation bar and the flash region. This is what your pages use.

### The Page Side

Every page imports a layout and wraps its body in it:

```html+jinja
{# myapp/views/card/show.jx #}
{#import "layouts/app.jx" as Layout #}
{#def card #}

<Layout title="Card details">
  <h1>{{ card.title }}</h1>
  <p>{{ card.body }}</p>
</Layout>
```

`<Layout>` is `app.jx`. The page's `<h1>` and `<p>` become its `content`. Anything between `<Layout>` and `</Layout>` is what shows up in the layout's main region.

### The `app.jx` Layout

A simplified version of the generated `app.jx`:

```html+jinja
{# myapp/views/layouts/app.jx #}
{#import "nav.jx" as Nav #}
{#import "flashes.jx" as Flashes #}
{#import "./base.jx" as Layout #}

<Layout attrs={{ attrs }}>
  <Nav />
  <Flashes />
  {{ content }}
</Layout>
```

It does three things:

- Wraps the page's content with `<Layout>` (= `base.jx`).
- Inserts the navigation and flash regions before the content.
- Forwards `attrs` to `base.jx` so attributes set by the page (like `class="dashboard"`) end up on the `<body>` tag.

### The `base.jx` Layout

`base.jx` is the actual HTML document:

```html+jinja
{# myapp/views/layouts/base.jx #}
{#def title = '', description = '', lang = 'en' #}

<!DOCTYPE html>
<html lang="{{ lang }}">
<head>
  <meta charset="utf-8">
  <title>{{ title }}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">

  {% for url in assets.collect_css() -%}
    <link rel="stylesheet" href="{{ url_for('assets', file=url) }}">
  {% endfor -%}

  {{ render_importmap() }}
  <script src="{{ url_for('assets', file='js/app.js') }}" type="module"></script>

  {% for url in assets.collect_js() -%}
    <script src="{{ url_for('assets', file=url) }}" type="module"></script>
  {% endfor -%}
</head>
<body {{ attrs.render() }}>
  {{ content }}
</body>
</html>
```

It accepts a few props (`title`, `description`, `lang`), collects every component's CSS and JS, emits the import map, and puts the page content in `<body>`.

### The Three-Level Stack

For a page that does `<Layout title="Card details">...</Layout>`, the call stack is:

```
page.jx                     ← calls <Layout> = app.jx
  └─ app.jx                  ← calls <Layout> = base.jx, with Nav and Flashes around content
       └─ base.jx             ← renders the HTML document, places content in <body>
```

The page's content gets nested inside `app.jx`'s slot, which gets nested inside `base.jx`'s slot, which renders the final HTML.

You don't need to know this structure to write pages - the page just imports `layouts/app.jx`, calls `<Layout>`, and stops thinking about it. But knowing the layers helps when you want to change something specific:

- Edit `base.jx` for the HTML document shape (title, meta tags, asset loading).
- Edit `app.jx` for what wraps every page (nav, flashes, footer).
- Edit a specific page for its own content.

### Multiple Layouts

Add a layout file to `views/layouts/` and pages can import it instead of (or alongside) `app.jx`:

```html+jinja
{# myapp/views/layouts/admin.jx #}
{#import "nav_admin.jx" as AdminNav #}
{#import "./base.jx" as Layout #}

<Layout attrs={{ attrs }}>
  <AdminNav />
  <main class="Admin">{{ content }}</main>
</Layout>
```

Admin pages then do `{#import "layouts/admin.jx" as Layout #}` instead of importing `app.jx`. Same shape, different chrome.

### Conditional Layout Sections

Layouts are regular components, so any Jinja control flow works. A common pattern is to skip the navigation when there's no current user:

```html+jinja
{#import "nav.jx" as Nav #}
{#import "./base.jx" as Layout #}

<Layout attrs={{ attrs }}>
  {% if current.user %}
    <Nav />
  {% endif %}
  {{ content }}
</Layout>
```

Or a "minimal" mode the page can opt into via a prop:

```html+jinja
{#import "nav.jx" as Nav #}
{#import "./base.jx" as Layout #}
{#def minimal=False #}

<Layout attrs={{ attrs }}>
  {% if not minimal %}
    <Nav />
  {% endif %}
  {{ content }}
</Layout>
```

```html+jinja
{# call site #}
<Layout title="Sign in" minimal>
  ...
</Layout>
```

Anything you can do in a regular component, a layout can do.

### Navigation Highlighting

The `<Nav>` component is a regular Jx component. To mark which link is active, use the `url_is` and `url_startswith` template globals:

```html+jinja
{# myapp/views/nav.jx #}
<nav class="Nav">
  <a href="{{ url_for('Card.index') }}"
     class="{% if url_startswith('Card.index') %}active{% endif %}">
    Cards
  </a>
  <a href="{{ url_for('Setting.show') }}"
     class="{% if url_is('Setting.show') %}active{% endif %}">
    Settings
  </a>
</nav>
```

`url_is(name)` returns `True` if the *current request* matched the named route exactly. `url_startswith(name)` returns `True` if it matched the named route or a route that starts with the same path - useful for "highlight Cards even on `/cards/42`."

---

## Template Globals in Proper

Every template (page, layout, component) has access to a small set of globals without importing anything. These come from two places: Proper itself, and Jx.

### The Globals

| Global              | Provided by | What it does                                                  |
| ------------------- | ----------- | ------------------------------------------------------------- |
| `url_for`           | Proper      | Generate URLs from named routes.                              |
| `url_is`            | Proper      | True if the current request matches a named route exactly.    |
| `url_startswith`    | Proper      | True if the current request matches a named route or a sub-path of it. |
| `current`           | Proper      | The per-request global context (covered below).               |
| `render_importmap`  | Proper      | Emit the `<script type="importmap">` for the `IMPORT_MAP` config. |
| `assets`            | Jx          | The asset collector (`render`, `render_css`, `render_js`, `collect_css`, `collect_js`). |
| `_get_random_id`    | Jx          | Generate a unique HTML id (used internally by some helpers). |

That's the full set in a base Proper application. Addons (i18n, auth) and your own code can add more.

### The `current` Object

`current` is a per-request global that holds context any template might need:

```html+jinja
{% if current.user %}
  Hello, {{ current.user.name }}.
{% else %}
  <a href="{{ url_for('Session.new') }}">Sign in</a>
{% endif %}
```

The standard attributes:

| `current.<attr>`     | What it is                                                              |
| -------------------- | ----------------------------------------------------------------------- |
| `current.app`        | The Proper application instance.                                        |
| `current.request`    | The current `Request` object.                                           |
| `current.response`   | The current `Response` object.                                          |
| `current.user`       | The signed-in user, or `None`. Set by the auth concern.                 |
| `current.auth_session` | The current auth session, or `None`. Set by the auth concern.         |
| `current.locale`     | The current locale string, or `None`. Set by the i18n addon.            |
| `current.timezone`   | The current timezone, or `None`. Set by the i18n addon.                 |
| `current.csrf_token` | The current CSRF token. Set by the `RequestForgeryProtection` concern.  |

`current.user`, `current.auth_session`, `current.locale`, and `current.timezone` always work - they return `None` when not set, rather than raising. The others raise `AttributeError` if accessed in a context where they weren't initialized; in a normal request that doesn't happen.

`current` is implemented with `contextvars`, so each request has its own values without you passing them around manually. A component used on a page sees the same `current.user` as the page itself.

### Flash Messages

Flash messages live on the request, not as a top-level global:

```html+jinja
{% set flashes = current.request.flashes %}
{% if flashes %}
  <div class="Flashes">
    {% for kind, message in flashes %}
      <div class="Flash Flash-{{ kind }}">{{ message }}</div>
    {% endfor %}
  </div>
{% endif %}
```

The generated `flashes.jx` does roughly that. `flashes` is a list of `(kind, message)` tuples; `kind` is a free-form string (`"info"`, `"success"`, `"warning"`, `"error"` by convention).

### Translation and Formatting Helpers

#### The `_` translator

`_` is always available in templates. It's a callable that resolves a key against the loaded translations:

```html+jinja
<h1>{{ _("welcome") }}</h1>
<p>{{ _("greeting", name=user.name) }}</p>
<p>{{ _("apples", count=cart.item_count) }}</p>
```

Without the `i18n` blueprint installed, no translation files are loaded, so `_("welcome")` returns `"welcome"` unchanged - the template still renders, you just see the keys. With `proper install i18n`, the `config/locales/` directory is read on startup and lookups resolve normally; the `CurrentLocale` and `CurrentTimezone` concerns wire the active locale into each request.

The full translator surface (pluralization, missing keys, locale resolution) is covered in the [Internationalization guide](/docs/i18n).

#### Formatting filters

A set of Babel-backed formatting filters is also always available, regardless of whether the `i18n` blueprint is installed. They format against the current locale and timezone, falling back to `LOCALE_DEFAULT` / `TIMEZONE_DEFAULT` from `config/main.py` when the i18n concerns aren't running.

```html+jinja
<time>{{ event.starts_at | format_datetime }}</time>
<time>{{ event.starts_at | format_date(format="full") }}</time>
<span>{{ event.duration | format_timedelta }}</span>

<span>{{ product.price | format_currency("USD") }}</span>
<span>{{ stats.rate | format_percent }}</span>
<span>{{ stats.total | format_decimal }}</span>

<span>{{ attachment.byte_size | format_size }}</span>

<p>{{ attendees | format_list }}</p>
```

The full set: `format_datetime`, `format_date`, `format_time`, `format_timedelta`, `format_skeleton`, `format_list`, `format_decimal`, `format_compact_decimal`, `format_currency`, `format_compact_currency`, `format_percent`, `format_scientific`, `format_size`. Each filter takes the same keyword arguments as the matching `app.i18n.format_*` method - see the [Internationalization guide](/docs/i18n) for the per-filter options.

### Controller Instance Attributes

Beyond the globals, every instance attribute set on the controller becomes a template variable:

```python
def show(self):
    self.card = Card.get_by_id(self.params["card_id"])
    self.related = Card.select().where(...).limit(5)
```

In `card/show.jx`:

```html+jinja
<h1>{{ card.title }}</h1>
{% for r in related %}
  <a href="{{ url_for('Card.show', r) }}">{{ r.title }}</a>
{% endfor %}
```

There's no manual context dictionary to assemble. If you wrote `self.foo = ...` in the action, the template uses `{{ foo }}`.

This works because Proper renders the template with `**vars(self)` - everything assigned to the controller instance flows into the template. Class-level properties (like `self.app` and `self.params`) aren't in `vars(self)`, so the template reaches for `current.app` and `current.request` instead.

---

## What's Not Covered Here

This guide focuses on the day-to-day surface: writing components, using them, and the way Proper hooks into Jx. A few topics are deliberately left out.

- **The Catalog API.** Proper sets up the catalog automatically, registers your `views/` folder, and adds the globals discussed above. If you're embedding Jx into a non-Proper context (a Flask app, a script that produces HTML) you'd build the catalog yourself - that's covered in the [Jx documentation](https://jx.scaletti.dev/){target="_blank"}.
- **Form rendering.** The `<Form>` component, render helpers like `field.label()` and `field.text_input()`, and the wire format for submitted data are covered in the [Rendering Forms guide](/docs/form_rendering).
