---
title: Static Assets
description: |
  Static assets are the CSS, JavaScript, images, and fonts your pages need. This guide explains where they live, how Proper serves them, and how filename fingerprinting lets browsers cache them aggressively without ever showing a stale version.
number_headers: true
---

# Static Assets

In this guide, you will learn how Proper serves the files your pages reference - stylesheets, scripts, images, fonts, and the occasional `robots.txt`.

- Where assets live in a Proper application.
- How `router.static()` mounts them.
- How `url_for("assets", file=...)` produces URLs with cache-busting fingerprints.
- How import maps let you `import` JS packages with no bundler.
- How `Cache-Control` and `Last-Modified` make repeat requests cheap.
- How to off-load file serving to nginx or another proxy in production.
- How to add multiple asset directories or serve from a CDN.

This guide is focused on the *delivery* of static files. For the Jx side - declaring component-level CSS and JS dependencies with `{#css #}` and `{#js #}` directives - see the [Jx Components and Layouts guide](/docs/jx_components).

---

## Introduction

A static asset is any file your application sends back as bytes, exactly as it sits on disk. CSS, JavaScript, images, fonts, PDFs, even `robots.txt` - if the bytes never change between request and response, it's a static asset.

Proper serves them with three pieces, all wired up by the new-app generator:

- A **route** declared in `myapp/router.py` with `router.static()`.
- A built-in `StaticFilesController` that opens the file and writes the right cache headers.
- A **filename fingerprinting** convention that adds a hash to URLs (`base-a1b2...css`) so browsers can cache forever and still see updates within a second of you saving the file.

Most of the time you don't think about any of this. You drop a CSS file in `assets/css/`, write `{{ url_for("assets", file="css/base.css") }}` in a template, and it works. The rest of this guide explains what's happening underneath, and the small set of options for when the defaults don't fit.

---

## Where Assets Live

A new application starts with this layout:

```
myapp/
├── assets/
│   ├── 500.html
│   ├── humans.txt
│   ├── icon.png
│   ├── icon.svg
│   ├── robots.txt
│   ├── fonts/
│   ├── images/
│   ├── js/
│   │   ├── application.js
│   │   ├── nestedform.js
│   │   └── vendor/
│   │       ├── stimulus.js
│   │       └── turbo.js
│   └── css/
│       ├── base.css
│       ├── buttons.css
│       ├── email.css
│       ├── error-page.css
│       ├── forms.css
│       ├── globals.css
│       ├── not-found-page.css
│       └── reset.css
```

The convention is one subdirectory per file type (`css/`, `js/`, `images/`, `fonts/`), with a few files at the root: `robots.txt`, `humans.txt`, and the `icon.png`/`icon.svg` favicons the browser looks for. There's also a `500.html` that Proper serves as the bare-bones error page when the application itself crashes too hard to render its own template.

You're not locked into this layout. The only thing that matters is that the files live somewhere reachable from `app.assets_path`, which defaults to `<your-app>/assets/`. Add new subdirectories whenever you want.

:::note | What's already in `assets/js`
The default `js/` directory ships with two vendored libraries under `js/vendor/` (`turbo.js`, `stimulus.js`), the `nestedform.js` helper, and an `application.js` entry point for your own code. They're not pulled from a CDN at runtime - they're real files in your app, served alongside everything else. This avoids a third-party DNS lookup on every page load.
:::

---

## The `router.static()` Route

A new application's `router.py` includes one line that sets up asset serving:

```python
# myapp/router.py
router.static(app.config.ASSETS_URL, root=app.assets_path, name="assets")
```

That's the entire wire-up. `ASSETS_URL` defaults to `/assets/`, so a request for `/assets/css/base.css` is served from `myapp/assets/css/base.css`.

The signature is:

```python
router.static(
    url,
    *,
    root,
    name=None,
    allowed_ext=(),
    public=True,
    fingerprint=True,
    host=None,
    defaults=None,
)
```

The arguments you'll touch most often:

| Argument        | Default | Purpose                                                                 |
| --------------- | ------- | ----------------------------------------------------------------------- |
| `url`           | -       | The URL prefix the assets live under (e.g. `/assets/`).                 |
| `root`          | -       | The directory on disk where the files are. Use `app.assets_path` if you can. |
| `name`          | `None`  | The route name, used by `url_for`. The generator uses `"assets"`.       |
| `fingerprint`   | `True`  | Insert a content hash into URLs for cache-busting (covered in [Filename Fingerprinting](#filename-fingerprinting)). |
| `allowed_ext`   | `()`    | Restrict to a specific list of extensions; empty means everything goes. |
| `public`        | `True`  | Whether to send `Cache-Control: public` (vs `private`).                 |

`router.static()` mounts a route under the hood that matches anything under the prefix - the path is `:file<path>`, where `<path>` is a custom placeholder that captures slashes. So `/assets/css/forms/buttons.css` works without any extra wiring.

:::tip
Prefer `app.assets_path` over hard-coding the path. It's set to `<your-app>/assets/` at startup, but tests and CLI scripts may overwrite it - using the attribute keeps your route in sync.
:::

---

## Generating Asset URLs

Don't write asset URLs by hand. Use `url_for("assets", file=...)` so the right fingerprint gets inserted:

```python
app.url_for("assets", file="css/base.css")
# /assets/css/base-a1b2c3d4...css
```

The same call works in templates (where `url_for` is a global):

```html+jinja
<link rel="stylesheet" href="{{ url_for('assets', file='css/base.css') }}">

<img src="{{ url_for('assets', file='images/logo.png') }}" alt="Logo">

<script src="{{ url_for('assets', file='js/application.js') }}" type="module"></script>
```

Pass the file path *relative to the asset root* - no leading slash, no `/assets/` prefix. The route's URL prefix gets prepended for you.

If the file doesn't exist on disk at the moment `url_for` runs, the URL is generated without a fingerprint. This is occasionally useful (build pipelines that produce assets just-in-time), but more often it's a sign you have a typo - the URL still gets emitted, but the file 404s when the browser fetches it.

---

## Import Maps

An *import map* is a small piece of JSON that tells the browser how to resolve `import` statements in ES modules. Without it, every `import` has to use a relative path (`./utils.js`) or an absolute URL. With it, you can write:

```javascript
// myapp/assets/js/application.js
import { Application } from "@hotwired/stimulus"
import "@hotwired/turbo"

const app = Application.start()
```

and the browser knows where `@hotwired/stimulus` and `@hotwired/turbo` actually live. No bundler required.

Import maps are a native browser feature, supported in every modern browser. Proper exposes them through one config key and one layout helper.

### The `IMPORT_MAP` Config

Set `IMPORT_MAP` in your config to a dict of `bare-name -> file-or-URL`:

```python
# config/main.py
IMPORT_MAP = {
    "@hotwired/stimulus": "js/vendor/stimulus.js",
    "@hotwired/turbo":    "js/vendor/turbo.js",
}
```

The new-app generator pre-populates this with Stimulus and Turbo, since those are the JS libraries the default `application.js` reaches for. Add or remove entries as your app evolves.

The keys are *bare module specifiers* - the strings you'd write in an `import` statement. Conventionally they look like npm package names (`@scope/name` or just `name`), but any string the JS spec accepts is fine.

### How URLs Are Resolved

Each value in `IMPORT_MAP` can be one of three shapes, and Proper treats them differently:

| Value                              | Treated as                                | Result                          |
| ---------------------------------- | ----------------------------------------- | ------------------------------- |
| `"js/vendor/stimulus.js"`          | path relative to `app.assets_path`        | fingerprinted URL via `url_for("assets", file=...)` |
| `"/assets/vendor/foo.js"`          | absolute path on your domain              | used verbatim, no fingerprint   |
| `"https://cdn.example.com/x.js"`   | full URL                                  | used verbatim, no fingerprint   |

The relative-path case is the interesting one - those entries flow through the same fingerprinting machinery as the rest of your assets, so updating `assets/js/vendor/stimulus.js` automatically invalidates the cached import-map URL.

:::error | Beware of the initial "/"
`/js/vendor/stimulus.js` is not the same as `js/vendor/stimulus.js`!
:::

### Rendering in the Layout

The generated base layout calls `render_importmap()`:

```html+jinja
{# myapp/views/layouts/base.jx #}
<head>
  ...
  {{ render_importmap() }}

  <script src="{{ url_for('assets', file='js/vendor/turbo.js') }}" type="module"></script>
  <script src="{{ url_for('assets', file='js/application.js') }}" type="module"></script>
</head>
```

Which produces a single compact `<script>` tag (shown wrapped here for readability):

```html
<script type="importmap" data-turbo-track="reload">{"imports": {"@hotwired/stimulus": "/assets/js/vendor/stimulus-a1b2c3...js", "@hotwired/turbo": "/assets/js/vendor/turbo-d4e5f6...js"}}</script>
```

`render_importmap()` is a global available in every template; no import needed.

:::warning | Order matters
The `<script type="importmap">` tag must appear *before* the first `<script type="module">` that uses the bare names it declares. The browser parses import maps eagerly and refuses to apply them retroactively. The default layout is already arranged correctly; if you write your own, keep `render_importmap()` ahead of your module scripts.
:::

### Adding an external Library

For a library you don't want to vendor, point an entry at its URL:

```python
IMPORT_MAP = {
    "@hotwired/stimulus": "js/vendor/stimulus.js",
    "@hotwired/turbo":    "js/vendor/turbo.js",
    "lodash-es":          "https://esm.sh/lodash-es@4.17.21",
}
```

Now `import _ from "lodash-es"` in your `application.js` resolves to esm.sh; the browser fetches it once and caches forever. The URL is passed through verbatim - no fingerprinting (the URL itself already encodes the version), no static-route round-trip.

### Why This Beats a Bundler

The traditional answer to "I need to import npm packages from my JS" is webpack, esbuild, Vite, or another bundler. The bundler walks your import graph, downloads dependencies, and produces one or two final JS files.

Import maps remove the bundler from the picture for the use case Proper targets - server-rendered apps with a sprinkle of progressive-enhancement JavaScript:

- **Faster reload** - no bundler to run; save a JS file, refresh the page, see the change. The browser fetches the changed file and the unchanged dependencies stay in cache.
- **Simpler deploy** - no `node_modules`, no `dist/` directory, no separate build step in CI. Vendor the libraries you depend on in `assets/js/` and they ship with the rest of your app.
- **Better debugging** - the source you wrote is the source the browser runs. Stack traces line up with files on disk.

For larger JS apps - SPAs, anything with hundreds of components, anything that needs tree-shaking or code-splitting - a bundler still pulls its weight. For everything else, the import map plus a few vendored files is enough.

---

## Filename Fingerprinting

A fingerprinted URL looks like:

```
/assets/css/base-a1b2c3d4e5f6a7b8c9...css
```

The hex string between the filename and the extension is a SHA-256 of the file's last-modified time. When you save the file, the mtime changes, the hash changes, and so does the URL. Browsers see a new URL and fetch the new bytes; old bookmarks and cached HTML still work because the underlying file is also reachable at its plain name.

### Why Fingerprint

Two reasons, both about caching:

- **Cache forever** - browsers can hold onto a fingerprinted asset until they need the disk space, with no risk of serving a stale copy. The next deploy gets fresh URLs, the browser fetches once, and that's it.
- **Skip revalidation** - even with a long `max-age`, browsers like to send `If-Modified-Since` requests "just to check." Fingerprinted URLs let Proper return `Cache-Control: immutable`, which tells the browser not to bother.

The result is that your CSS and JS load from the local cache on every page after the first one, without any 304 round-trips.

### What Goes Into the Hash

The hash is over the file's `st_mtime` (last-modified time) on the filesystem, not the file's content. This is fast, and good enough for the cache-busting use case: any change to the file triggers a new mtime, which triggers a new hash, which triggers a new URL.

The trade-off is that touching a file without changing it (a `git checkout`, a `chmod`, certain build pipelines) also changes the hash. Browsers refetch a file that didn't actually change. This is rarely a problem in practice - the file is small and gzipped on the wire.

### Disabling Fingerprinting

For the few cases where you need a stable URL - an Open Graph image referenced by a Slack preview, an email's signature image - pass `fingerprint=False`:

```python
router.static("/og", root=app.root_path / "assets" / "og", name="og", fingerprint=False)
```

Now `url_for("og", file="cover.png")` returns `/og/cover.png` with no hash. The cache headers also change (covered in the next section).

---

## Cache-Control Headers

`StaticFilesController` writes one of two cache-control headers depending on whether the URL was fingerprinted.

### Fingerprinted Files

```
Cache-Control: max-age=31536000, public, immutable
```

- `max-age=31536000` is one year - the longest a sane browser will cache.
- `public` lets shared caches (CDNs, corporate proxies) cache too.
- `immutable` tells the browser "do not even revalidate" - skip the `If-Modified-Since` round-trip.

This is the headline result of fingerprinting: your assets are served once, then served from cache forever.

### Non-Fingerprinted Files

```
Cache-Control: max-age=0, public, must-revalidate
Last-Modified: <mtime>
```

- `max-age=0` means the cached copy is always considered stale.
- `must-revalidate` forces the browser to check before using it.
- `Last-Modified` lets Proper answer the check with `304 Not Modified` if nothing changed.

The browser still has to make an HTTP request, but Proper returns a tiny `304` response with no body if the file is unchanged. It's slower than fingerprinted assets but keeps the bytes-on-the-wire down.

### Public vs Private

`public=True` (the default) tells caches between the user and your server (CDNs, ISP proxies, corporate gateways) that they may cache the response. That's what you want for assets that look the same to everyone.

If for some reason you serve user-specific files through `router.static()` - generally a bad idea, but possible - flip `public=False`:

```python
router.static(
    "/private",
    root="/var/per-user",
    name="private_assets",
    public=False,
)
```

Now the `Cache-Control` says `private` instead of `public`, and shared caches will refuse to keep a copy.

:::warning | User-specific files don't belong here
`router.static()` reads files straight from disk and skips authorization checks. If a file's URL is the same for all users, but the *content* depends on who's asking, you need a regular controller that loads the right file after checking permissions. The `public=False` flag adjusts the cache header but doesn't add any access control.
:::

### The CORS Header

The static controller also sets one more header on every response:

```
Access-Control-Allow-Origin: *
```

This makes assets reachable from JavaScript on other origins - useful when your CSS or fonts are served from a CDN and your HTML is served from your primary domain. Static assets are public by definition, so opening them up is safe.

---

## Restricting File Types

By default, anything under `app.assets_path` is fair game. If your asset directory mixes built outputs with source files (a Tailwind project that keeps `_tw.css` source alongside `tailwind.css` output, for example), you can restrict serving to specific extensions:

```python
router.static(
    "/assets/",
    root=app.assets_path,
    name="assets",
    allowed_ext=[".css", ".js", ".png", ".jpg", ".svg", ".woff2"],
)
```

A request for any file with a different extension (or no extension at all) returns `404 Not Found`. Include `""` in the list if you want to allow files without extensions.

`allowed_ext` is a defense-in-depth measure, not a substitute for putting source files in a different directory. The right structure for most apps is a separate `src/` (your sources) and `assets/` (built outputs) - then `allowed_ext` becomes redundant because the source files were never under the asset root in the first place.

---

## Off-loading to a Reverse Proxy

In production, opening a file and copying its bytes to a socket is something nginx, Caddy, or Apache do significantly faster than a Python ASGI process. The trick is to let the proxy serve the file *while keeping the routing logic in Proper* - your application still decides whether the file exists and what cache headers it deserves; it just doesn't send the bytes itself.

That's what `STATIC_X_SENDFILE_HEADER` configures. Set it in your config:

```python
# config/main.py
class Config:
    ...
    STATIC_X_SENDFILE_HEADER = "X-Accel-Redirect"  # nginx, Caddy
    # or:
    # STATIC_X_SENDFILE_HEADER = "X-Sendfile"      # Apache, Lighttpd
```

When set, Proper's response no longer carries the file bytes. Instead, it sends an empty body plus the configured header pointing at an internal path. The proxy intercepts the response, opens the file itself, and streams it to the client.

The header values you'll need:

| Server  | Header              |
| ------- | ------------------- |
| nginx   | `X-Accel-Redirect`  |
| Caddy   | `X-Accel-Redirect`  |
| Apache  | `X-Sendfile`        |
| Lighttpd| `X-Sendfile`        |

The proxy needs configuration on its side, too - nginx requires an `internal;` location block, Apache needs `mod_xsendfile` enabled. The [Deployment and Performance guide](/docs/deployment) covers the proxy-side configuration; this guide just shows the Proper-side switch.

:::tip | When to bother
For a small site, the bytes Proper writes vs the bytes nginx writes are indistinguishable. The off-load matters when assets are large (videos, big PDFs), or when traffic is high enough that the Python process spends real time reading files. Until then, leave `STATIC_X_SENDFILE_HEADER` empty.
:::

---

## Root-Level Assets

Some files are conventionally fetched from the root of your domain:

- `robots.txt` - search engines look here.
- `humans.txt` - the friendly equivalent for the curious.

You don't want to mount a separate static route for each of them, but they also can't live under `/assets/` without redirects. The generator's `router.py` handles this with two explicit redirects:

```python
# myapp/router.py
router.get("robots.txt", redirect="/assets/robots.txt")
router.get("humans.txt", redirect="/assets/humans.txt")
```

The browser asks for `/robots.txt`, gets a `307` to `/assets/robots.txt`, and gets the file (with fingerprinting and caching) from there. It's two requests instead of one on the first hit.

For other root-level files, add another `router.get(..., redirect=...)` line.

The favicon doesn't need a root redirect at all. The default layout points the browser straight at the fingerprinted asset with `<link rel="icon">` tags, so there's no `/favicon.ico` round-trip:

```html+jinja
<link rel="icon" href="{{ url_for('assets', file='icon.png') }}" type="image/png">
<link rel="icon" href="{{ url_for('assets', file='icon.svg') }}" type="image/svg+xml">
```

:::note
Of course you can, *and should*, configure this at proxy level (nginx, Caddy, etc.), but the redirects makes it works during development.
:::

---

## Multiple Asset Directories

`router.static()` can be called more than once. Each call mounts a separate route with its own root, name, and options:

```python
# myapp/router.py
router.static(
    "/assets/",
    root=app.assets_path,
    name="assets",
)

# A second mount for files generated at runtime, with different cache rules
router.static(
    "/exports/",
    root=app.root_path / "var/exports",
    name="exports",
    fingerprint=False,
    allowed_ext=[".pdf", ".csv"],
    public=False,
)
```

Now `url_for("assets", file=...)` and `url_for("exports", file=...)` go to different places with different headers.

Common reasons to add a second route:

- **Generated files** - reports, exports, user-uploaded thumbnails - that need different lifecycle rules.
- **Vendored content** - documentation, a help center, marketing pages - that lives outside the main asset tree.
- **Per-feature directories** that you want to serve from a CDN with a different domain.

For user-uploaded files (avatars, attachments) you usually want the [File Storage](/docs/storage) module instead - it adds authorization, image variants, and S3 support. `router.static()` is the right answer when the files are *yours*, not the users'.

---

## Using a CDN to Serve Assets

CDN stands for Content Delivery Network. A CDN stores copies of your assets in computers close to your users, so a user in Sydney isn't waiting on bytes from a server in Frankfurt.

It's best practice to place a CDN in front of your Proper application to serve assets in production.

### The Configuration

Set `ASSETS_URL` to the full CDN URL, with a trailing slash:

```python
# config/main.py
ASSETS_URL = "https://cdn.example.com/"
```

That's the entire change on Proper's side. `url_for("assets", file="css/base.css")` now returns `https://cdn.example.com/css/base-<hash>.css`, and every other code path that builds an asset URL (the Jx `{#css #}` and `{#js #}` directives, `render_importmap()` for relative-path entries, your own template URL helpers) follows along.

### Origin Pull vs. Push Deploy

CDNs come in two flavors. Both work the same with Proper:

- **Origin pull.** The CDN holds nothing until the first request. When a user fetches `https://cdn.example.com/css/app-abc.css`, the CDN fetches it from your application server (the *origin*), caches it, and returns it. Future fetches at any edge hit the cache. Cloudflare, Fastly, and Bunny all work this way out of the box. Setup is one DNS record and the `ASSETS_URL` change.
- **Push deploy.** You upload assets to a bucket (S3, Cloud Storage) at deploy time, and the CDN fronts the bucket. The application server is never touched for static files. CloudFront-on-S3 is the canonical example. Setup is more involved (a CI step, IAM permissions) but the result is even less load on the origin.

In origin-pull mode, the first user pays a small latency cost while the CDN populates its cache; subsequent users hit the edge directly. In push-deploy mode, the cache is warm from the moment a deploy completes.

Fingerprinting handles cache invalidation either way: a new deploy produces new URLs, the CDN treats them as new files, and the old URLs stay valid for already-cached HTML. **You never need to "purge" the CDN.** The old asset just stops being requested as the old HTML rolls out of caches.

### What the CDN Should Honor

A few things to verify when picking or configuring a CDN:

- **`Cache-Control: immutable`** must pass through. Most CDNs honor it; a few older configurations strip it. Test once after switching: open DevTools, look at a fingerprinted asset's response headers, confirm `immutable` is still there.
- **`Access-Control-Allow-Origin: *`** is set automatically by Proper. The CDN should pass it through unmodified, so cross-origin font and image fetches work. Cloudflare and Fastly do this by default; some configurations require explicit allow-list rules.
- **`Last-Modified`** for the rare non-fingerprinted asset (an OG image, a `humans.txt`). The CDN should pass this header through and respect `If-Modified-Since` revalidation.
- **Compression** (gzip, brotli) for text assets. Modern CDNs do this transparently.

### Relative URLs Inside CSS

CSS files often reference other assets with relative URLs:

```css
@font-face {
  font-family: "Inter";
  src: url("../fonts/inter.woff2") format("woff2");
}
```

These still work when the CSS is served from the CDN: the browser resolves the relative URL against the CSS file's own URL, which is also on the CDN. No `url_for` substitution needed inside CSS, no special build step, no rewriting of paths.

The exception is if the relative URL points at something *not* fingerprinted. The font file in the example above gets cached by mtime on the CDN, but its URL doesn't change when the file changes - so the browser's cached copy of the CSS will keep pointing at the old font URL, which the CDN will keep serving. Touch the CSS to bust its cache, or move the fonts under a fingerprinted prefix, depending on which is more practical.

### The First Deploy

There's nothing special to do on a first deploy in origin-pull mode. The CDN starts empty, the first user to hit each asset triggers a fetch from your origin, and you're warm within a few requests.

For push deploy, you'll want a step in your release pipeline that uploads the contents of `assets/` to the bucket. The classic shape is `aws s3 sync assets/ s3://my-cdn-bucket/`. Run it after Proper has built any generated assets (Tailwind output, sprite sheets) and before traffic starts flowing to the new release.

---

## Asset Helpers in Jx

Jx components can declare their CSS and JS dependencies with two directives:

```html+jinja
{#css "card.css", "card-anim.css" #}
{#js "card.js" #}
{#def title #}

<div class="card">{{ content }}</div>
```

When this component appears on a page, Jx collects the declarations and the layout renders them as `<link>` and `<script>` tags - which in turn use `url_for("assets", file=...)` to fingerprint the URLs.

So while the directives live in Jx, the URLs they produce flow through everything in this guide: same fingerprinting, same cache headers, same routes. The full directive surface is covered in the [Jx Components and Layouts guide](/docs/jx_components#assets).
