---
title: Turbo
description: |
  Turbo on the server: fast navigation with Drive, page sections with Frames, and
  live partial updates with Streams - all from your Jx templates, with little or
  no custom JavaScript.
number_headers: true
---

# Turbo

In this guide you will learn how to use Turbo from the server side of a Proper app.

Turbo bundles several techniques for creating fast and modern web applications. With Turbo, you let the server deliver HTML directly - the contents of a frame, and individual stream fragments - so you rarely write JavaScript.

Turbo comes in four pieces:

Piece       | What it does                                                           | What Proper gives you
----------- | ---------------------------------------------------------------------- | ---------------------
**Drive**   | Turns every link and form into a fast partial navigation, no reload    | On by default - nothing to write
**Frames**  | Wraps part of a page so Turbo can navigate and replace it on its own   | `turbo_frame_tag`, `request.turbo_frame`
**Streams** | Applies targeted changes to the page from a form response or broadcast | the `turbo_stream` builder, `*.turbo_stream.jx` views, `render(stream=...)`
**Native**  | Wraps your HTML in iOS and Android shells                              | nothing special - your normal responses serve native too

Drive needs no server code, Frames need a little, and Streams are where the backend does the real work. Turbo Native is out of scope here - it consumes the same HTML responses you already return.

---

## Turbo Drive

Turbo Drive watches every same-origin link click and form submission, fetches the new page in the background, and swaps in its `<body>` without a full reload. You get SPA-like navigation with no custom JavaScript. It loads from the bundled library in your layout:

```html+jinja
<script src="{{ url_for('assets', file='js/vendor/turbo.js') }}"
  type="module"></script>
```

Once that script is on the page, every link and form on your site is accelerated automatically. There is nothing to opt *into*. The import map and asset setup that make this work are covered in [Assets](/docs/assets).

To opt a specific link or form *out* - a third-party widget, a file download, a page Turbo cannot handle - set `data-turbo="false"`:

```html
<a href="/export.csv" data-turbo="false" download>Download CSV</a>
```

### Links with HTTP Methods

By default, link clicks send a GET request to your server. But you can change this with data-turbo-method:

```html
<a href="/articles/54" data-turbo-method="delete">Delete the article</a>
```

### Confirm to Navigate

Decorate links with both data-turbo-confirm and data-turbo-method, and confirmation will be required for a visit to proceed.

```html
<a href="/articles" data-turbo-method="get"
  data-turbo-confirm="Do you want to leave this page?"
>Back to articles</a>

<a href="/articles/54" data-turbo-method="delete"
  data-turbo-confirm="Are you sure you want to delete the article?"
>Delete the article</a>
```

Use `Turbo.config.forms.confirm = confirm` to change the method that gets called for confirmation. The default is the browser’s built in `confirm`.

### Form Submissions

Turbo Drive handles form submissions in a manner similar to link clicks. The key difference is that form submissions can issue stateful requests using the HTTP POST method, while link clicks only ever issue stateless HTTP GET requests.

Throughout a submission, Turbo Drive will dispatch a series of events that target the `<form>` element and bubble up through the document:

1. `turbo:submit-start`
2. `turbo:before-fetch-request`
3. `turbo:before-fetch-response`
4. `turbo:submit-end`

During a submission, Turbo Drive will set the “submitter” element's disabled attribute when the submission begins, then remove the attribute after the submission ends.

When submitting a `<form>` element, browsers will treat the `<input type="submit">` or `<button>` element that initiated the submission as the submitter. To submit a `<form>` element programmatically, invoke the `HTMLFormElement.requestSubmit(`) method and pass an `<input type="submit">` or `<button>` element as an optional parameter.

If there are other changes you’d like to make during a `<form>` submission (for example, disabling all fields within a submitted `<form>`), you can declare your own event listeners:

```js
addEventListener("turbo:submit-start", ({ target }) => {
  for (const field of target.elements) {
    field.disabled = true
  }
})
```

### More

Drive also shows a progress bar for slow navigations and caches a preview of visited pages for instant back and forward. For the deeper options - morphing page refreshes, visit control, scroll handling - see the [Turbo Drive handbook](https://turbo.hotwired.dev/handbook/drive).

---

## Turbo Frames

A frame is a region of the page that Turbo can replace on its own. Wrap content in `turbo_frame_tag` (a template global, so there is no import) and give it a stable id. Use it as an expression for an empty or lazily loaded frame, or as a `{% call %}` block to wrap content:

```html+jinja
{% call turbo_frame_tag(message) %}
  <h1>{{ message.title }}</h1>
  <a href="{{ url_for('Message.edit', object=message) }}">Edit</a>
{% endcall %}
{# <turbo-frame id="message_42"> ... </turbo-frame> #}
```

The id ties everything together. [`dom_id`](/docs/view_helpers#dom_id) derives the id from the object (`message_42`)

The rule Turbo follows is simple: **when a link or form inside a frame navigates, Turbo finds the `<turbo-frame>` with the *same id* in the response and swaps in just that.** So the edit link above loads `/messages/42/edit`, and Turbo pulls the `message_42` frame out of that response - the rest of the page is left alone.

This means you don't have to change anything in your controllers code for this mechanism to work.

### Inline editing

The classic frame pattern is an edit link that swaps the frame for a form, and a form that swaps it back. Every view wraps the same `dom_id` frame, so Turbo keeps swapping the one region:

```html+jinja {title="views/message/show.jx (view state)"}
{% call turbo_frame_tag(message) %}
  <h1>{{ message.title }}</h1>
  <a href="{{ url_for('Message.edit', object=message) }}">Edit</a>
{% endcall %}
```

```html+jinja {title="views/message/edit.jx (edit state)"}
{% call turbo_frame_tag(message) %}
  <form method="post" action="{{ url_for('Message.update', object=message) }}">
    <input name="title" value="{{ message.title }}">
    <button>Save</button>
  </form>
{% endcall %}
```

The controller needs no Turbo awareness. `update` saves and redirects to `show` as usual - Turbo follows the redirect, extracts the `message_42` frame, and the region flips back to view mode:

```python {title="controllers/message_controller.py"}
def update(self):
    message = self.form.save()
    self.response.redirect_to("Message.show", message)
```

When the form is invalid, the generated `validate_form` callback re-renders `edit.jx` with a `422` status , so Turbo swaps the form, errors and all, back into the frame. Still no Turbo-specific code.

### Lazy-loading a frame

Give a frame a `src` and Turbo fetches it; add `loading="lazy"` and it waits until the frame scrolls into view. The frame shows a placeholder until the content arrives, which is handy for slow widgets that should not block the main page:

```html+jinja {title="views/dashboard/index.jx"}
{% call turbo_frame_tag(
  "inbox_count", src=url_for("Inbox.count"), loading="lazy"
) %}
  Loading...
{% endcall %}
```

The endpoint returns the same-id frame with the real content (and no `src`):

```html+jinja {title="views/inbox/count.jx"}
{% call turbo_frame_tag("inbox_count") %}{{ unread }} unread{% endcall %}
```

### Targeting and breaking out

By default a link inside a frame navigates *that* frame. Two attributes on the link change the target, written as plain HTML:

```html
<a href="/messages/42" data-turbo-frame="_top">
  Open full page</a>
<a href="/messages/42" data-turbo-frame="other_frame">
  Load into another frame</a>
```

`_top` promotes the click to a normal full-page Drive visit; a frame id loads the response into that other frame instead.

To make a frame's *own* navigations add browser history (so the "Back" button works), set `data-turbo-action="advance"` on the frame. `turbo_frame_tag` turns keyword underscores into dashes, so you pass it as `data_turbo_action`:

```html+jinja
{% call turbo_frame_tag("results", data_turbo_action="advance") %}
  ...
{% endcall %}
```

### Frame requests on the server

Turbo sends a `Turbo-Frame` header carrying the frame's id on every frame navigation. Read it with `request.turbo_frame`, which returns that id (or `None` for a normal request):

```python {title="controllers/message_controller.py"}
def show(self):
    if self.request.turbo_frame:
        # just the frame, skip the layout
        return self.render("message/_card.jx")
    # otherwise the full page renders implicitly
```

:::note
You rarely need this. Turbo extracts the matching frame from whatever you return, so a normal full-page response already works - it just sends bytes Turbo throws away. Branch on `request.turbo_frame` only when you want to skip the layout and render the bare frame. Proper does not strip the layout for frame requests automatically.
:::

---

## Turbo Streams

A stream is a list of targeted DOM operations: append a row, replace an element, remove a node, etc. The same fragment serves two delivery paths: as the **response to a form submission**, or **broadcast** to subscribed clients over the cable. You build it once, and Proper renders it from your Jx components exactly like a full page.

### The turbo_stream builder

`turbo_stream` (in `proper.turbo`, re-exported as `proper.turbo_stream`) builds `<turbo-stream>` fragments. Call an action method with a target and the content to render:

```python
from proper import turbo_stream

turbo_stream.append("messages", "message/message.jx", message=message)
# <turbo-stream action="append" target="messages">
#   <template>
#     ...rendered message.jx...
#   </template>
# </turbo-stream>
```

The action methods map one-to-one to Turbo's:

Method                | Effect
--------------------- | --------------------------------------------------------
`append` / `prepend`  | Add the fragment as the last / first child of the target
`replace` / `update`  | Replace the whole element / just its inner content
`before` / `after`    | Insert the fragment outside the target, before / after it
`remove`              | Delete the target (renders no content)
`morph`               | Replace by morphing, preserving focus and scroll
`refresh`             | Trigger a full Turbo page refresh (no target)

The first argument is the **target**: an element id, or a model. A model is converted with `dom_id` (`dom_id(post)` → `post_42`). To act on many elements at once, pass `targets=` with a CSS selector instead:

```python
# target="post_42"
turbo_stream.replace(post, "post/post.jx", post=post)
# targets=".flash", no content
turbo_stream.remove(targets=".flash")
```

For **what goes inside**, you have three options, checked in this order - pick one:

Argument               | Renders
---------------------- | -------------------------------------------------
`component="path.jx"`  | the Jx component through the catalog, like `self.render`
`content=...`          | a string or `Markup`, or a callable returning one
`html=...`             | ready-made HTML

In a template, the action methods also work as `{% call %}` blocks - the block body becomes the content:

```html+jinja
{% call turbo_stream.append("messages") %}
  <li>{{ message.body }}</li>
{% endcall %}
```

To send several operations at once, concatenate fragments. They are `Markup`, so `+` just works:

```python
turbo_stream.append("messages", "message/message.jx", message=msg) \
    + turbo_stream.update("new_message", "message/form.jx")
```

The instance is also callable for the positional form, `turbo_stream("append", target, ...)`, which is equivalent to the matching method.

### Responding to a form

When a Turbo-driven form submits, Turbo adds `text/vnd.turbo-stream.html` to the `Accept` header.

Proper registers that as the `turbo_stream` format, so the resolver routes the request to a `{action}.turbo_stream.jx` view automatically, falling back to the normal `.jx` template when there is not one:

```
views/message/create.turbo_stream.jx <- Turbo form submission
views/message/create.jx              <- normal navigation (fallback)
```

A `*.turbo_stream.jx` view is just a list of fragments, with no layout. The most common scenario - create a row, then reset the form - reuses the same partials the full page already uses:

```html+jinja {title="views/message/create.turbo_stream.jx"}
{{ turbo_stream.append("messages", "message/message.jx", message=message) }}
{{ turbo_stream.update("new_message", "message/form.jx") }}
```

The controller does not change. It sets the data and lets the template resolve:

```python {title="controllers/message_controller.py"}
def create(self):
    self.message = self.form.save()
    # Turbo request  -> create.turbo_stream.jx;
    # normal request -> create.jx
```

To build the response inline instead of in a view, return `render(stream=...)` with one fragment or a list. It sets the `text/vnd.turbo-stream.html` content type and joins them:

```python {title="controllers/message_controller.py"}
def delete(self):
    self.message.delete_instance()
    return self.render(stream=turbo_stream.remove(self.message))
```

When one URL serves both Turbo and normal clients, branch on `request.turbo_stream`:

```python {title="controllers/message_controller.py"}
def create(self):
    self.message = self.form.save()
    if self.request.turbo_stream:
        return self.render(stream=turbo_stream.append(
            "messages", "message/message.jx", message=self.message,
        ))
    self.response.redirect_to("Message.index")
```

The three everyday scenarios are append-on-create, `replace` on update, and `remove` on delete - each rendering (or, for remove, naming) the same partial the list uses.

### Broadcasting live updates

The same fragment can be pushed to every subscribed client instead of returned to one. Broadcast it over the cable from a controller, a background task, or anywhere you have the app:

```python
from proper import turbo_stream

app.cable.broadcast(
    f"room_{room.id}",
    turbo_stream.append(
      "messages",
      "message/message.jx",
      message=message
    ),
)
```

Clients subscribe with a `<turbo-stream-channel>` element, and each fragment is applied for you - there is no `received()` handler to write. The channel, the subscription element, and stream-name authorization are part of the Channels addon: see [Channels - Broadcasting HTML](/docs/channels#broadcasting-html-turbo-streams).

:::note
Broadcasts are explicit - call `app.cable.broadcast` wherever a change happens.
:::

---

## Quick reference

These are available in every view, with no import:

Global             | Use
------------------ | ---------------------------------------------------------
`turbo_stream`     | build `<turbo-stream>` fragments
`turbo_frame_tag`  | render a `<turbo-frame>` (expression or `{% call %}` block)
`dom_id`           | stable element id for a model, `dom_id(post)` → `post_42`

And on the request and response:

Name                   | Type         | Meaning
---------------------- | ------------ | ----------------------------------------------------
`request.turbo_stream` | `bool`       | the client accepts `text/vnd.turbo-stream.html`
`request.turbo_frame`  | `str / None` | the `Turbo-Frame` header - the id of the frame being updated
`self.render(stream=)` | -            | set the Turbo Stream content type and return one or a list of fragments

---

## Related

- [Turbo Handbook](https://turbo.hotwired.dev/handbook/introduction).
- [Jx Components](/docs/jx_components) - the server-rendered components you wrap in a frame or a stream.
- [View Helpers](/docs/view_helpers#dom_id) - `dom_id` and the other template globals.
- [Controllers](/docs/controllers) - rendering, redirects, and the request cycle.
- [Real-Time Updates (Channels)](/docs/channels) - the WebSocket cable behind broadcasting.
- [Assets](/docs/assets) - import maps and how `turbo.js` is loaded.
