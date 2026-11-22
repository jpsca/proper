import base64
import hashlib
import inspect
import json
import typing as t

import inflection
from markupsafe import Markup

from ..global_context import current


def importmap_json(app) -> str:
    """The import map of the app, as the JSON `render_importmap` writes in
    its script: the `IMPORT_MAP` setting, with the URLs of the assets."""
    importmap = app.config.get("IMPORT_MAP", {})
    imports = {}
    for key, value in importmap.items():
        if value.startswith(("http", "/")):
            imports[key] = value
        else:
            imports[key] = app.url_for("assets", file=value)
    return json.dumps({"imports": imports})


def csp_hash(text: str) -> str:
    """The source that allows an inline script or style with exactly this
    text in a `Content-Security-Policy`: `'sha256-...'`, with its quotes.
    The text is what is between the tags, every space and line break
    included."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return f"'sha256-{base64.b64encode(digest).decode('ascii')}'"


def csp_nonce() -> str:
    """The nonce of this visitor, for the `nonce` attribute of an inline
    `<script>` or `<style>` (see `Response.csp_nonce`)."""
    return current.response.csp_nonce


def csp_meta_tag() -> str:
    """A `<meta name="csp-nonce">` tag with the nonce of this visitor.

    Turbo reads it, and gives the nonce to the `<style>` of its progress
    bar and to the scripts of the pages it loads. The nonce is in the
    `nonce` attribute, which the browser hides from the CSS selectors, not
    in `content`.
    """
    return Markup(f'<meta name="csp-nonce" nonce="{csp_nonce()}">')


def render_importmap(_app) -> str:
    """Render a script tag containing the import map for the app's assets.

    An import map is a JSON object that maps module specifiers to URLs, allowing
    you to use bare module specifiers in your JavaScript code. For example, with
    the following import map:

    ```html
    <script type="importmap">
    {
        "imports": {
            "my-lib": "/static/my-lib.js"
        }
    }
    </script>
    ```

    You can import `my-lib` in your JavaScript code like this:
`
    ```javascript`
    import { something } from "my-lib";
    ```

    The `render_importmap` function generates a script tag with the import map based on
    the app's configuration. It looks for an `IMPORT_MAP` configuration variable, which
    should be a dictionary mapping module specifiers to asset paths or URLs.

    The script is inline. With a `Content-Security-Policy`, allow it with
    `app.importmap_csp_hash` in `script-src`.

    """
    json_imports = importmap_json(_app)
    tags = f'<script type="importmap" data-turbo-track="reload">{json_imports}</script>'
    # Without a proxy in front, the cable listens on its own port; the
    # client (`cable.js`) reads it from here.
    if _app.config.DEBUG and _app.config.get("CABLE_PORT"):
        tags += f'\n<meta name="cable-port" content="{int(_app.config.CABLE_PORT)}">'
    return Markup(tags)


def dom_id(*parts: t.Any) -> str:
    """Generate a stable id for a collection of objects and/or strings, suitable
    for use in HTML element ids.

    All parts will be converted to strings and joined with underscores.
    If a part is an object, its class name and primary key (if available) will be used
    to generate a string for that part. Composite primary keys are also supported.

    ```python
    dom_id(Post.get(45))                     # => "post_45"
    dom_id(Post.get(45), "edit")             # => "post_45_edit"
    dom_id(Post.get(45), "edit", "special")  # => "post_45_edit_special"
    ```

    If there is no primary key, the class name is prefixed with "new_" instead.

    ```python
    dom_id(Post.create())  # => "new_post"
    ```

    If the object has a `to_key()` method, it will be used to get the key instead of the primary key.
    This allows you to customize the key generation for privacy-sensitive or more complex models.
    If this method returns `None`, `False`, or an empty value, the object will be treated as if it
    has no primary key. If it returns a composite key (tuple), the parts will be joined with underscores.

    If the object is a class rather than an instance, only the class name is used:

    ```python
    dom_id(Post)            # => "post"
    dom_id(Post, "custom")  # => "post_custom"
    ```

    Arguments:
        parts:
            The objects to generate a DOM id for. Can be strings, model instances, or classes.

    """
    JOINER = "_"
    result = []

    for part in parts:
        if isinstance(part, str):
            result.append(part)
        elif inspect.isclass(part):
            name = inflection.underscore(part.__name__)
            result.append(name)
        else:
            name = inflection.underscore(part.__class__.__name__)
            key = _record_key_for_dom_id(part, JOINER)
            if not key:
                result.append(f"new{JOINER}{name}")
            else:
                result.append(f"{name}{JOINER}{key}")

    return JOINER.join(result)


def _record_key_for_dom_id(obj: t.Any, JOINER: str) -> str:
    """Get the key to use in a DOM id for a model instance. By default, this is the primary key,
    but if the object has a `to_key()` method, it will be used instead.
    """
    if hasattr(obj, "to_key") and callable(obj.to_key):
        key = obj.to_key()
    elif hasattr(obj, "_pk") and obj._pk is not None:
        key = obj._pk
    else:
        key = ""

    if not key and str(key) != "0":
        return ""

    if isinstance(key, tuple):
        return JOINER.join(str(part) for part in key)
    else:
        return str(key)
