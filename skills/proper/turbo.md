---
title: Turbo
description: Turbo on the server — Drive navigation, Frames, and Streams (the turbo_stream builder, *.turbo_stream.jx responses, render(stream=), broadcasting, and the request predicates)
last_verified: 2026-06-15
---

# Turbo

Proper bundles [Turbo](https://turbo.hotwired.dev) and gives its server side first-class helpers. The whole point of Turbo is *HTML over the wire*: your Jx views render full pages, the contents of a frame, and individual stream fragments — all from the same templates, with little or no custom JavaScript.

Turbo has four pieces. You meet them in roughly this order of effort:

| Piece | What it does | What Proper gives you |
|-------|--------------|------------------------|
| **Drive** | Turns every link and form into a fast partial navigation, no reload | On by default — nothing to write ([Turbo Drive](#turbo-drive)) |
| **Frames** | Wrap part of a page so Turbo can navigate and replace it on its own | `turbo_frame_tag`, `request.turbo_frame` ([Turbo Frames](#turbo-frames)) |
| **Streams** | Apply targeted DOM changes from a form response or a broadcast | `turbo_stream` builder, `*.turbo_stream.jx`, `render(stream=)` ([Turbo Streams](#turbo-streams)) |
| **Native** | Wrap your HTML in iOS/Android shells | Nothing special — your normal responses serve native too |

Drive needs no server code; Frames need a little; Streams are where the backend does real work. Native is out of scope for this guide — it consumes the same HTML responses you already return.

## Table of Contents

- [Turbo Drive](#turbo-drive)
- [Turbo Frames](#turbo-frames)
- [Turbo Streams](#turbo-streams)
  - [The turbo_stream builder](#the-turbo_stream-builder)
  - [Responding to a form](#responding-to-a-form)
  - [Broadcasting live updates](#broadcasting-live-updates)
- [Quick reference](#quick-reference)

## Turbo Drive

Turbo Drive intercepts same-origin link clicks and form submissions, fetches the new page in the background, and swaps in its `<body>` without a full reload — SPA-like navigation with zero custom JavaScript. It is loaded from the bundled library in your layout:

```html+jinja
<script src="{{ url_for('assets', file='js/vendor/turbo.js') }}" type="module"></script>
```

Once that script is on the page, every link and form on your site is accelerated automatically. There is nothing to opt *into*.

To opt a specific link or form *out* — a third-party widget, a file download, a page Turbo can't handle — set `data-turbo="false"`:

```html
<a href="/export.csv" data-turbo="false">Download CSV</a>
```

Because Drive never does a full reload, the `<head>` from the first page sticks around. When you ship new CSS or JS you need the browser to notice, mark those tags with `data-turbo-track="reload"` — Turbo forces a full reload when they change. Proper's `render_importmap()` already emits its tag with `data-turbo-track="reload"`, so an import-map change busts the page automatically; add the attribute to your own tracked assets:

```html+jinja
<link rel="stylesheet" href="{{ url_for('assets', file='css/app.css') }}" data-turbo-track="reload">
```

Drive also shows a progress bar for slow navigations and caches a preview of visited pages for instant back/forward. For the deeper options (morphing page refreshes, visit control, scroll handling) see the [Turbo Drive handbook](https://turbo.hotwired.dev/handbook/drive). The frontend setup (layout, import maps, assets) lives in [frontend.md](frontend.md#import-maps).

## Turbo Frames

A frame is a region of the page Turbo can replace on its own. Wrap content in `turbo_frame_tag` — a [template global](#quick-reference), so no import — and give it a stable id. Use it as an expression for an empty/lazy frame, or as a `{% call %}` block to wrap content:

```html+jinja
{% call turbo_frame_tag(message) %}
  <h1>{{ message.title }}</h1>
  <a href="{{ url_for('Message.edit', object=message) }}">Edit</a>
{% endcall %}
{# <turbo-frame id="message_42"> … </turbo-frame> #}
```

The id is what ties everything together. Pass a model and `turbo_frame_tag` derives it with [`dom_id`](frontend.md#template-globals) (`message_42`); pass strings and they're joined with `_`. **The rule Turbo follows: when a link or form inside a frame navigates, Turbo finds the `<turbo-frame>` with the *same id* in the response and swaps in just that.** So the edit link above loads `/messages/42/edit`, and Turbo pulls the `message_42` frame out of that response — the rest of the page is left alone.

### Inline editing

The canonical frame pattern: an edit link that swaps the frame for a form, and a form that swaps it back. Every view wraps the same `dom_id` frame, so Turbo keeps swapping the one region:

```html+jinja {title="views/message/show.jx — view state"}
{% call turbo_frame_tag(message) %}
  <h1>{{ message.title }}</h1>
  <a href="{{ url_for('Message.edit', object=message) }}">Edit</a>
{% endcall %}
```

```html+jinja {title="views/message/edit.jx — edit state"}
{% call turbo_frame_tag(message) %}
  <form method="post" action="{{ url_for('Message.update', object=message) }}">
    <input name="title" value="{{ message.title }}">
    <button>Save</button>
  </form>
{% endcall %}
```

The controller needs no Turbo awareness. `update` saves and redirects to `show` as usual — Turbo follows the redirect, extracts the `message_42` frame, and the region flips back to view mode:

```python
def update(self):
    message = self.form.save()
    self.response.redirect_to("Message.show", message)
```

When the form is invalid, the generated `validate_form` before-callback calls `self.redo()` — re-rendering `edit.jx` with a `422` — so Turbo swaps the error-laden form back into the frame. Still no Turbo-specific code.

### Lazy-loading a frame

Give a frame a `src` and Turbo fetches it; add `loading="lazy"` and it waits until the frame scrolls into view. The frame renders a placeholder until the content arrives — handy for slow widgets that shouldn't block the main page:

```html+jinja {title="the dashboard"}
{{ turbo_frame_tag("inbox_count", src=url_for("Inbox.count"), loading="lazy") }}
```

The endpoint returns the same-id frame with the real content (and no `src`):

```html+jinja {title="views/inbox/count.jx"}
{% call turbo_frame_tag("inbox_count") %}{{ unread }} unread{% endcall %}
```

### Targeting and breaking out

By default a link inside a frame navigates *that* frame. Two attributes on the link override the target — written as plain HTML:

```html
<a href="/messages/42" data-turbo-frame="_top">Open full page</a>
<a href="/messages/42" data-turbo-frame="other_frame">Load into another frame</a>
```

`_top` promotes the click to a normal full-page Drive visit; a frame id loads the response into that other frame instead.

To make a frame's *own* navigations push browser history (so Back works), set `data-turbo-action="advance"` on the frame. `turbo_frame_tag` turns keyword underscores into dashes, so pass it as `data_turbo_action`:

```html+jinja
{% call turbo_frame_tag("results", data_turbo_action="advance") %} … {% endcall %}
```

### Frame requests on the server

Turbo sends a `Turbo-Frame` header with the frame's id on every frame navigation. Read it with `request.turbo_frame` (the id string, or `None` for a normal request):

```python
def show(self):
    # self.message is set by a before-callback
    if self.request.turbo_frame:
        return self.render("message/_card.jx")  # just the frame, skip the layout
    # otherwise the full page renders implicitly
```

**You rarely need this.** Turbo extracts the matching frame from whatever you return, so a normal full-page response already works — it just sends bytes Turbo throws away. Branch on `request.turbo_frame` only when you want to skip the layout and render the bare frame. Proper does *not* strip the layout for frame requests automatically.

## Turbo Streams

A stream is a list of targeted DOM operations — append a row, replace an element, remove a node. The same fragment serves two delivery paths: as the **response to a form submission**, or **broadcast** to subscribed clients over the cable. You build it once and Proper reuses your Jx components to render it, exactly like a full page.

### The turbo_stream builder

`turbo_stream` (in `proper.turbo`, re-exported as `proper.turbo_stream`) builds `<turbo-stream>` fragments. Call an action method with a target and the content to render:

```python
from proper import turbo_stream

turbo_stream.append("messages", "message/Message.jx", message=message)
# <turbo-stream action="append" target="messages"><template>…Message.jx…</template></turbo-stream>
```

The actions map one-to-one to Turbo's:

| Method | Effect |
|--------|--------|
| `append` / `prepend` | Add the fragment as the last / first child of the target |
| `replace` / `update` | Replace the whole element / just its inner content |
| `before` / `after` | Insert the fragment outside the target, before / after it |
| `remove` | Delete the target (renders no content) |
| `morph` | Replace via Turbo 8 morphing (keeps focus and scroll) |
| `refresh` | Trigger a full Turbo page refresh (no target) |

**Target.** The first argument is an element id, or a model — a model is converted with `dom_id` (`dom_id(post)` → `post_42`). To act on many elements at once, pass `targets=` with a CSS selector instead:

```python
turbo_stream.replace(post, "post/Post.jx", post=post)   # target="post_42"
turbo_stream.remove(targets=".flash")                   # targets=".flash", no content
```

**What goes inside.** Three ways, checked in this order — pick one:

| Argument | Renders |
|----------|---------|
| `component="path.jx"` (or 2nd positional) + props | The Jx component, through the catalog — same as `self.render` |
| `content=…` | A string/`Markup`, or a callable returning one |
| `html=…` | Ready-made HTML |

In a template, the action methods double as `{% call %}` blocks — the block body becomes the content:

```html+jinja
{% call turbo_stream.append("messages") %}
  <li>{{ message.body }}</li>
{% endcall %}
```

**Concatenate** to send several operations at once. Fragments are `Markup`, so `+` (or returning a list to `render(stream=)`) just works:

```python
turbo_stream.append("messages", "message/Message.jx", message=msg) \
    + turbo_stream.update("new_message", "message/Form.jx")
```

The instance is also callable for the positional form — `turbo_stream("append", target, …)` — equivalent to the matching method.

### Responding to a form

When a Turbo-driven form submits, Turbo adds `text/vnd.turbo-stream.html` to the `Accept` header. Proper registers that as the `turbo_stream` format, so the [implicit resolver](controllers.md#implicit-template-rendering) routes the request to a `{action}.turbo_stream.jx` view automatically — falling back to the normal `.jx` template when there isn't one:

```
views/message/create.turbo_stream.jx   ← Turbo form submission
views/message/create.jx                 ← normal navigation (fallback)
```

A `*.turbo_stream.jx` view is just a list of fragments, no layout. The create-a-row scenario — append the new message and reset the form — reuses the same `Message.jx` and `Form.jx` partials the full page uses:

```html+jinja {title="views/message/create.turbo_stream.jx"}
{{ turbo_stream.append("messages", "message/Message.jx", message=message) }}
{{ turbo_stream.update("new_message", "message/Form.jx") }}
```

The controller doesn't change — it sets the data and lets the template resolve:

```python
def create(self):
    self.message = self.form.save()
    # Turbo request → create.turbo_stream.jx; normal request → create.jx
```

To build the response inline instead of in a view, return `render(stream=…)` with one fragment or a list. It sets the `text/vnd.turbo-stream.html` Content-Type and joins them:

```python
def delete(self):
    self.message.delete_instance()
    return self.render(stream=turbo_stream.remove(self.message))
```

When an action serves both Turbo and normal clients from one URL, branch on `request.turbo_stream`:

```python
def create(self):
    self.message = self.form.save()
    if self.request.turbo_stream:
        return self.render(stream=turbo_stream.append(
            "messages", "message/Message.jx", message=self.message,
        ))
    self.response.redirect_to("Message.index")
```

The three everyday scenarios are append-on-create, `replace` on update, and `remove` on delete — each rendering (or, for remove, naming) the same partial the list uses.

> Coming from Rails, there is no `respond_to` block and no `format.turbo_stream`. Accept-based template resolution and the `request.turbo_stream` predicate cover the same ground.

### Broadcasting live updates

The same fragment can be pushed to every subscribed client instead of returned to one. Broadcast it over the cable from a controller, a background task, or anywhere you have the app:

```python
from proper import turbo_stream

app.cable.broadcast(
    f"room_{room.id}",
    turbo_stream.append("messages", "message/Message.jx", message=message),
)
```

Clients subscribe with a `<turbo-stream-channel>` element, and each fragment is applied by `Turbo.renderStreamMessage` — no `received()` handler to write. The channel, subscription element, and stream-name authorization are part of the channels addon: see [channels.md, Turbo Streams](channels.md#turbo-streams).

Proper does **not** ship Rails-style model callbacks (`broadcasts_to`, `after_create_commit`) — broadcasts are explicit. Call `app.cable.broadcast` wherever the change happens.

## Quick reference

Template globals (every view, no import):

| Global | Use |
|--------|-----|
| `turbo_stream` | build `<turbo-stream>` fragments |
| `turbo_frame_tag` | render a `<turbo-frame>` (expression or `{% call %}` block) |
| `dom_id` | stable element id for a model — `dom_id(post)` → `post_42` ([frontend.md](frontend.md#template-globals)) |

Request predicates and the response helper:

| Name | Type | Meaning |
|------|------|---------|
| `request.turbo_stream` | `bool` | the client accepts `text/vnd.turbo-stream.html` (a Turbo Stream request) |
| `request.turbo_frame` | `str \| None` | the `Turbo-Frame` header — the id of the frame being updated, else `None` |
| `self.render(stream=…)` | — | set the Turbo Stream Content-Type and return one or a list of fragments |

The MIME constant is `proper.constants.TURBO_STREAM_MIME` (re-exported as `proper.turbo.TURBO_STREAM_MIME`).
