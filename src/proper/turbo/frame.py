import typing as t
from collections.abc import Callable

from markupsafe import Markup, escape

from ..helpers import dom_id


def turbo_frame_tag(
    *ids: t.Any,
    src: str = "",
    loading: str = "",
    target: str = "",
    caller: Callable[[], t.Any] | None = None,
    **attrs: t.Any,
) -> Markup:
    """Render a `<turbo-frame>`, the unit Turbo navigates and replaces on its own.

    `ids` build the frame's id: strings are used as-is, model instances are
    converted with `dom_id`, and several are joined with `_`.

    Use it two ways from a template. As an expression for an empty or lazily
    loaded frame:

    ```html+jinja
    {{ turbo_frame_tag(post, src=url_for("Posts.show", post=post), loading="lazy") }}
    ```

    or as a `{% call %}` block to wrap content:

    ```html+jinja
    {% call turbo_frame_tag(post) %}
      {{ post.title }}
    {% endcall %}
    ```

    `src` loads the frame's content from a URL, `loading="lazy"` defers that load
    until the frame scrolls into view, and `target` sends the frame's own
    navigations to another frame. Any extra keyword becomes an attribute, with
    underscores turned into dashes (`data_turbo="false"` -> `data-turbo="false"`).
    """
    frame_id = "_".join(i if isinstance(i, str) else dom_id(i) for i in ids)
    parts = [f'id="{escape(frame_id)}"']
    if src:
        parts.append(f'src="{escape(src)}"')
    if loading:
        parts.append(f'loading="{escape(loading)}"')
    if target:
        parts.append(f'target="{escape(target)}"')
    for key, value in attrs.items():
        parts.append(f'{escape(key.replace("_", "-"))}="{escape(value)}"')

    inner = caller() if caller else ""
    return Markup(f'<turbo-frame {" ".join(parts)}>{inner}</turbo-frame>')
