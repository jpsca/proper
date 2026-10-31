---
title: Stimulus
description: |
  Stimulus in a Proper app: small JavaScript controllers attached to the HTML
  your Jx components already render, loaded only on the pages that use them.
number_headers: true
---

# Stimulus

In this guide you will learn how to add client-side behavior to a Proper app with Stimulus.

[Stimulus](https://stimulus.hotwired.dev) is a small JavaScript framework with a modest goal: it connects JavaScript objects, called *controllers*, to elements of the page through `data-` attributes. It does not render HTML. Your Jx components render the HTML on the server, and Stimulus adds the behavior - a dropdown that opens, a field that shows a character count, a form that saves itself.

That division is what makes Stimulus a good fit for a Proper app. Turbo (see the [Turbo guide](/docs/turbo)) brings HTML from the server; Stimulus handles the small amount of behavior that has to happen in the browser.

This page is a compact introduction with the parts that are specific to Proper. The [Stimulus handbook](https://stimulus.hotwired.dev/handbook/introduction) and [reference](https://stimulus.hotwired.dev/reference/controllers) cover every option in more depth.

---

## What You Already Have

A new Proper app comes with Stimulus set up:

- `assets/js/vendor/stimulus.js` is the library itself, vendored into your app so there is no CDN request at runtime.
- The `IMPORT_MAP` config maps the bare name `@hotwired/stimulus` to that file, so `import { Controller } from "@hotwired/stimulus"` works in any of your scripts with no bundler (see [Assets - Import Maps](/docs/assets#import-maps)).
- `assets/js/application.js` starts the Stimulus application and keeps it in `window.Stimulus`:

```js {title="assets/js/application.js"}
import { Application } from "@hotwired/stimulus"

window.Stimulus = Application.start()
```

The base layout loads `application.js` as a module after the import map, so `window.Stimulus` exists by the time any other script runs.

Proper does not scan a folder for controllers. Each controller registers itself, and each Jx component declares the controller files it needs. The next section shows how.

---

## Your First Controller

A controller is a JavaScript class in its own file. The example below hides and shows a panel when a button is clicked.

```js {title="assets/js/toggle-controller.js"}
import { Controller } from "@hotwired/stimulus"

class ToggleController extends Controller {
  static targets = ["panel"]

  toggle() {
    this.panelTarget.hidden = !this.panelTarget.hidden
  }
}

window.Stimulus.register("toggle", ToggleController)
```

The last line registers the class under the *identifier* `toggle`. That identifier is what the HTML uses to refer to the controller.

Then a Jx component declares the script with the `{#js #}` directive and uses the controller in its markup:

```html+jinja {title="myapp/views/disclosure.jx"}
{#js "js/toggle-controller.js" #}
{#def label #}

<div data-controller="toggle">
  <button type="button" data-action="toggle#toggle">{{ label }}</button>
  <div data-toggle-target="panel" hidden>
    {{ content }}
  </div>
</div>
```

Three attributes do all the work:

- `data-controller="toggle"` connects a `ToggleController` instance to the `<div>`. This element is the controller's *scope*.
- `data-action="toggle#toggle"` calls the `toggle()` method when the button is clicked.
- `data-toggle-target="panel"` marks the element the controller reaches through `this.panelTarget`.

The `{#js #}` directive is what ties a controller file to a component. The layout collects the scripts of every component used on the page and emits one `<script type="module">` for each, so a controller loads only on pages that render the component (see [Jx Components - Assets](/docs/jx_components#component-assets)). The path is relative to the `assets/` folder.

### Naming

Pick a short, kebab-case identifier that describes the behavior (`toggle`, `autosave`, `char-count`), and name the file after it: `assets/js/<identifier>-controller.js`. The identifier appears in every attribute, so a dash in it is written as is: `data-char-count-target`.

Name the controller after what it does, not where it is used. A `toggle` controller works on a menu, a sidebar, and a details panel. A `sidebar` controller works on one thing.

---

## The Building Blocks

### Targets

Targets are the elements a controller needs to reach. Declare them in `static targets` and mark them with `data-<identifier>-target`:

```js
static targets = ["input", "count"]
```

```html
<div data-controller="char-count">
  <textarea data-char-count-target="input"></textarea>
  <span data-char-count-target="count"></span>
</div>
```

For a target named `input`, the controller gets three properties:

Property                | Returns
----------------------- | ----------------------------------------
`this.inputTarget`      | the first matching element (an error if there is none)
`this.inputTargets`     | all matching elements, as an array
`this.hasInputTarget`   | `true` if at least one exists

A target must be inside the controller's element. Nested controllers with the same identifier do not see each other's targets.

### Actions

Actions connect DOM events to controller methods. The format of `data-action` is `event->identifier#method`:

```html
<input data-action="input->char-count#update">
```

Common elements have a default event, so you can leave it out: `click` for buttons and links, `input` for text fields and text areas, `change` for selects and checkboxes, `submit` for forms. The `toggle#toggle` of the first example relied on this.

Several actions go in the same attribute, separated by spaces. Two suffixes extend where an action listens:

- `@window` or `@document` listens on the window or the document instead of the element: `click@window->menu#close`.
- `.key` after a keyboard event filters by key: `keydown.esc->menu#close`, `keydown.enter`, `keydown.ctrl+s`.

Options after the method change the handling: `menu#close:prevent` calls `preventDefault()`, `:stop` calls `stopPropagation()`, `:once` runs the action one time.

A dropdown menu is the classic case. It opens on click, and closes on a click anywhere else or on the Escape key. Without Stimulus, that is three listeners to set up and remove by hand. With actions, it is markup:

```html+jinja {title="myapp/views/menu.jx"}
{#js "js/menu-controller.js" #}
{#def label #}

<div data-controller="menu"
     data-action="keydown.esc->menu#close click@window->menu#closeOutside">
  <button type="button" data-action="menu#toggle">{{ label }}</button>
  <div data-menu-target="panel" hidden>
    {{ content }}
  </div>
</div>
```

```js {title="assets/js/menu-controller.js"}
import { Controller } from "@hotwired/stimulus"

class MenuController extends Controller {
  static targets = ["panel"]

  toggle() {
    this.panelTarget.hidden = !this.panelTarget.hidden
  }

  close() {
    this.panelTarget.hidden = true
  }

  closeOutside(event) {
    if (!this.element.contains(event.target)) this.close()
  }
}

window.Stimulus.register("menu", MenuController)
```

Every action method receives the event. `event.target` is the element that fired it, and `event.params` holds any action parameters set on it as `data-<identifier>-<name>-param` attributes.

### Values

Values are typed settings read from `data-<identifier>-<name>-value` attributes. This is the way to pass data from your Python code to a controller:

```js
static values = {
  url: String,
  interval: { type: Number, default: 2000 },
  enabled: Boolean,
}
```

```html+jinja
<form data-controller="autosave"
      data-autosave-url-value="{{ url_for('Draft.update', object=draft) }}"
      data-autosave-interval-value="5000">
```

The controller reads `this.urlValue`, `this.intervalValue`, and `this.enabledValue`, converted to the declared type. Writing to `this.intervalValue` updates the attribute. Types are `String`, `Number`, `Boolean`, `Array`, and `Object`; the last two are read as JSON, so render them with Jinja's `tojson` filter: `data-chart-points-value="{{ points | tojson }}"`.

Define a method named `<name>ValueChanged(value, previousValue)` and Stimulus calls it when the value changes, and once when the controller connects.

### Classes

Classes keep CSS class names out of your JavaScript. The controller declares the names it needs, and the HTML supplies the actual classes:

```js
static classes = ["open"]

toggle() {
  this.element.classList.toggle(this.openClass)
}
```

```html
<div data-controller="menu" data-menu-open-class="is-open">
```

`this.openClass` returns the string, and `this.openClasses` returns an array when the attribute lists several classes separated by spaces.

### Outlets

Outlets let one controller talk to another by CSS selector:

```js
static outlets = ["result"]

search() {
  this.resultOutlets.forEach((result) => result.show())
}
```

```html
<div data-controller="search" data-search-result-outlet=".result">
```

`this.resultOutlet` is the first controller instance matching the selector, and `this.resultOutlets` is all of them. The target element must have its own `data-controller="result"`.

### Lifecycle Callbacks

Stimulus calls three methods on its own:

Method           | When
---------------- | ----------------------------------------------------------
`initialize()`   | once, the first time the controller is created
`connect()`      | each time the controller's element is attached to the document
`disconnect()`   | each time the element is removed from the document

Use `connect()` for setup that touches the page (start a timer, create an observer, focus a field) and `disconnect()` to undo it. Anything you add outside the controller's element in `connect()`, such as a listener on `window`, a `setInterval`, or a `ResizeObserver`, must be removed in `disconnect()`, or it will stay behind after the element is gone.

Targets have callbacks too: `<name>TargetConnected(element)` and `<name>TargetDisconnected(element)` run when a target is added to or removed from the page, which is how a controller notices rows that Turbo appended.

### Events Between Controllers

A controller can emit a DOM event with `this.dispatch("saved", { detail: { id } })`. The event is named `<identifier>:saved`, bubbles from the controller's element, and any other controller can listen with `data-action="autosave:saved->flash#show"`.

---

## Controllers and Jx Components

Jx components and Stimulus controllers pair well: one component renders the markup, one controller gives it behavior, and the `{#js #}` directive keeps them together. A few points help when you write the component.

**Attribute names.** Keyword arguments in Jx turn underscores into dashes when rendered as attributes. That matters for anything built through `attrs` or through tags that take keyword arguments, like `frame`:

```html+jinja
{% do attrs.set(data_controller="autosave", data_autosave_url_value=url) %}
<form {{ attrs.render() }}>
```

renders `data-controller="autosave" data-autosave-url-value="..."`. In plain HTML inside the component, write the dashes yourself.

**Form fields.** Formidable's field renderers accept extra attributes the same way, so you can attach a target or an action to the input they render. The password component of the auth addon does exactly this:

```html+jinja {title="password.jx (auth addon)"}
{#def field, label: str #}
{#js "js/show-password-controller.js" #}

{% do attrs.set(data_show_password_target="input") %}

<div class="password-field" data-controller="show-password">
  {{ field.label(label) }}
  {{ field.password_input(**attrs.as_dict) }}
  <button type="button"
    data-show-password-target="show"
    data-action="show-password#show">Reveal</button>
  <button type="button" class="hidden"
    data-show-password-target="hide"
    data-action="show-password#hide">Hide</button>
  {{ field.error_tag() }}
</div>
```

**One controller, many components.** Several components can declare the same `{#js #}` file. The layout emits the script once per page, and the controller connects to every element that names it.

**The addons as examples.** The auth addon ships `show-password-controller.js`, and the storage addon ships `file-input-controller.js` and `image-input-controller.js`. Installing an addon copies them into your `assets/js/`, so they are a good place to see real controllers that use targets, classes, and actions together.

---

## Stimulus and Turbo

Stimulus watches the document with a `MutationObserver`, so it does not care how an element arrived. This is what makes it work with Turbo without extra code:

- **Drive** replaces the `<body>` on every visit. Controllers on the old body are disconnected, controllers on the new body are connected. `connect()` runs again on every page that has the element.
- **Frames and Streams** insert and replace fragments. Controllers inside them connect as soon as the fragment lands, and `<name>TargetConnected` fires for new targets.
- **Scripts load once.** When a visit brings a page whose components declare a controller the current page did not have, Turbo adds the new `<script type="module">` to the `<head>`, and the browser runs it. Scripts already in the head are not run again, so `window.Stimulus.register` is called once per controller for the life of the browser tab.

Two consequences to keep in mind:

**Clean up in `disconnect()`.** Because Drive keeps the window alive between visits, a listener on `window` or a running interval does not go away when the page changes. Remove in `disconnect()` everything `connect()` created outside the element.

**The page snapshot comes first.** Before Drive replaces the body, it saves a snapshot of the current page to show on "Back" and as a preview. That happens *before* `disconnect()` runs, so changes you make in `disconnect()` do not reach the snapshot. To leave the page in a state that makes sense when it reappears, listen for the `turbo:before-cache` event:

```js
connect() {
  this.reset = this.reset.bind(this)
  document.addEventListener("turbo:before-cache", this.reset)
}

disconnect() {
  document.removeEventListener("turbo:before-cache", this.reset)
}

reset() {
  this.panelTarget.hidden = true
}
```

For elements that should simply not be in the snapshot, such as a flash message, the `data-turbo-temporary` attribute needs no JavaScript. See [Turbo - Cleanup before leaving](/docs/turbo#cleanup-before-leaving).

:::note
`application.js` also re-dispatches `DOMContentLoaded` on every `turbo:load`. That is for third-party scripts written for full page loads. Stimulus controllers do not need it; use `connect()` instead.
:::

---

## Patterns

### Split controllers to make them composable

Say you are asked for a personal bio field with a 280-character limit, and the spec calls for showing the character count, autosizing the text area, and autosaving the form.

You will likely need these behaviors elsewhere. So, instead of one `bio` controller that wraps all of them, write three: an `autosave` controller on the form, an `autosize` controller on the text area, and a `char-count` controller on a `<div>` that wraps the text area and the counter. Each one is small, works alone, and can be reused on the next form:

```html+jinja
<form data-controller="autosave" data-autosave-url-value="{{ url_for('Profile.update') }}">
  <div data-controller="char-count" data-char-count-max-value="280">
    <textarea name="bio"
      data-controller="autosize"
      data-char-count-target="input"
      data-action="input->char-count#update input->autosave#schedule"></textarea>
    <span data-char-count-target="count"></span>
  </div>
</form>
```

### Use actions instead of hand-written listeners

Keyboard shortcuts, clicks outside an element, and window events are all a `data-action` away: `keydown.esc->`, `click@window->`, `resize@window->`. Writing them as actions keeps the listeners in the markup, next to the element they belong to, and Stimulus removes them when the element goes away. Reach for `addEventListener` only for events Stimulus cannot express, and then always pair it with a removal in `disconnect()`.

### Keep state in the DOM

A controller is recreated on every Turbo visit, so state held in JavaScript properties does not survive navigation, and it is invisible to the server. Prefer values and classes: they live on the element, Turbo snapshots them, and a stream that replaces the element also resets them. Store in a JavaScript property only what has no meaning outside the current connection, like a timer id.

---

## Related

- [Stimulus Handbook](https://stimulus.hotwired.dev/handbook/introduction) and [Reference](https://stimulus.hotwired.dev/reference/controllers).
- [Turbo](/docs/turbo) - Drive, Frames, and Streams, and the patterns that pair with Stimulus.
- [Jx Components](/docs/jx_components) - the `{#js #}` directive and the `attrs` object.
- [Assets](/docs/assets) - import maps and how `stimulus.js` is served.
