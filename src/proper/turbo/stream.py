import typing as t
from collections.abc import Callable

from markupsafe import Markup, escape

from ..global_context import current
from ..helpers import dom_id


class TurboStream:
    """Build `<turbo-stream>` fragments, the unit of a Turbo Stream update.

    Call an action method with a `target` and either a Jx `component` (rendered
    through the catalog with its props), ready-made `content`, or raw `html`:

    ```python
    turbo_stream.append("messages", "Message.jx", message=msg)
    turbo_stream.replace(post, component="posts/Post.jx", post=post)
    turbo_stream.remove("message_1")
    ```

    `target` is an element id, or a model instance (its `dom_id` is used). Pass
    `targets` with a CSS selector instead to act on every matching element.

    `content` can be a string/`Markup` or a callable returning one - which is how
    the action methods double as `{% call %}` blocks in a template:

    ```html+jinja
    {% call turbo_stream.append("messages") %}
      <li>{{ message.body }}</li>
    {% endcall %}
    ```

    Broadcast the result over a stream for a live update, or return it from a
    controller as a `text/vnd.turbo-stream.html` response - the same fragment
    serves both. Concatenate several to send more than one operation at once.

    The instance is also callable - `turbo_stream("append", target, ...)` - which
    is equivalent to the matching action method.
    """

    def __call__(
        self,
        action: str,
        target: t.Any,
        component: str = "",
        *,
        html: str | Markup = "",
        targets: str | None = None,
        **props: t.Any,
    ) -> Markup:
        return self._render(
            action,
            target=target,
            targets=targets,
            component=component,
            html=html,
            **props,
        )

    def append(self, target=None, component="", *, targets=None, html="", **props):
        """Append the fragment as the last child of the target(s)."""
        return self._render(
            "append",
            target=target,
            targets=targets,
            component=component,
            html=html,
            **props,
        )

    def prepend(self, target=None, component="", *, targets=None, html="", **props):
        """Prepend the fragment as the first child of the target(s)."""
        return self._render(
            "prepend",
            target=target,
            targets=targets,
            component=component,
            html=html,
            **props,
        )

    def replace(self, target=None, component="", *, targets=None, html="", **props):
        """Replace the target element(s) entirely with the fragment."""
        return self._render(
            "replace",
            target=target,
            targets=targets,
            component=component,
            html=html,
            **props,
        )

    def update(self, target=None, component="", *, targets=None, html="", **props):
        """Replace the inner content of the target element(s)."""
        return self._render(
            "update",
            target=target,
            targets=targets,
            component=component,
            html=html,
            **props,
        )

    def remove(self, target=None, *, targets=None):
        """Remove the target element(s). No fragment is rendered."""
        return self._render("remove", target=target, targets=targets)

    def before(self, target=None, component="", *, targets=None, html="", **props):
        """Insert the fragment before the target element(s)."""
        return self._render(
            "before",
            target=target,
            targets=targets,
            component=component,
            html=html,
            **props,
        )

    def after(self, target=None, component="", *, targets=None, html="", **props):
        """Insert the fragment after the target element(s)."""
        return self._render(
            "after",
            target=target,
            targets=targets,
            component=component,
            html=html,
            **props,
        )

    def morph(self, target=None, component="", *, targets=None, html="", **props):
        """Morph the target element(s) into the fragment (Turbo 8 morphing)."""
        return self._render(
            "morph",
            target=target,
            targets=targets,
            component=component,
            html=html,
            **props,
        )

    def refresh(self, *, request_id: str = "") -> Markup:
        """Trigger a Turbo page refresh. Carries no target or fragment.

        Pass `request_id` to let the originating tab skip its own refresh.
        """
        attr = f' request-id="{escape(request_id)}"' if request_id else ""
        return Markup(f'<turbo-stream action="refresh"{attr}></turbo-stream>')

    # Private

    def _render(
        self,
        action: str,
        *,
        target: t.Any = None,
        targets: str | None = None,
        component: str = "",
        html: str | Markup = "",
        caller: Callable[[], t.Any] | None = None,
        **props: t.Any,
    ) -> Markup:
        if component:
            inner_html = current.app.catalog.render(component, **props)
        else:
            # `caller` is the html delivered by a template's `{% call %}` block.
            if caller:
                inner_html = caller()
            else:
                inner_html = html

        selector = self._selector(target, targets)
        inner = "" if action == "remove" else f"<template>{inner_html}</template>"
        return Markup(
            f'<turbo-stream action="{escape(action)}" {selector}>{inner}</turbo-stream>'
        )

    @staticmethod
    def _selector(target: t.Any, targets: str | None) -> str:
        if targets is not None:
            return f'targets="{escape(targets)}"'
        if not isinstance(target, str):
            target = dom_id(target)
        return f'target="{escape(target)}"'


turbo_stream = TurboStream()
