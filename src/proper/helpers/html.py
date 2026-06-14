import inspect
import json
import typing as t

import inflection
from markupsafe import Markup


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

    """
    importmap = _app.config.get("IMPORT_MAP", {})
    imports = {}
    for key, value in importmap.items():
        if value.startswith(("http", "/")):
            imports[key] = value
        else:
            imports[key] = _app.url_for("assets", file=value)

    json_imports = json.dumps({"imports": imports})
    return Markup(
        f'<script type="importmap" data-turbo-track="reload">{json_imports}</script>'
    )


def dom_id(obj: t.Any, prefix: str = "") -> str:
    """Generate a stable id for an object, suitable for use in HTML element ids.

    It uses the object's class name and primary key (if available) to generate a unique id.
    If there is no primary key, prefix with “new_” instead.

    ```python
    dom_id(Post.get(45))   # => "post_45"
    dom_id(Post.create())  # => "new_post"
    ```

    The `prefix` argument can be used to add a namespace to the id, for example:

    ```python
    dom_id(Post.get(45), "edit")  # => "edit_post_45"
    ```

    If the object has a `to_key()` method, it will be used to get the key instead of the primary key.
    This allows you to customize the key generation for privacy-sensitive or more complex models.

    If the object is a class rather than an instance, only the class name is used:

    ```python
    dom_id(Post)            # => "post"
    dom_id(Post, "custom")  # => "custom_post"
    ```

    Arguments:
        obj:
            The object to generate a DOM id for. Can be a model instance or a class.
        prefix:
            An optional string to prefix the id with, for namespacing.

    """
    JOIN = "_"
    prefix = f"{prefix}{JOIN}" if prefix else ""

    if inspect.isclass(obj):
        name = inflection.underscore(obj.__name__)
        key = ""
    else:
        name = inflection.underscore(obj.__class__.__name__)
        key = _record_key_for_dom_id(obj, JOIN)
        if not key:
            prefix = f"{prefix}new{JOIN}"

    key = f"{JOIN}{key}" if key else ""

    return f"{prefix}{name}{key}"


def _record_key_for_dom_id(obj: t.Any, JOIN: str) -> str:
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
        return JOIN.join(str(part) for part in key)
    else:
        return str(key)
