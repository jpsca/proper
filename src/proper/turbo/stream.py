import typing as t
from collections.abc import Callable

from markupsafe import Markup, escape

from ..global_context import current
from ..helpers import dom_id


class TurboStream:
    """Build `<turbo-stream>` fragments, the unit of a Turbo Stream update.

    Call an action method with a `target` and either a Jx `component` (rendered
    through the catalog with its props) or ready-made `html`:

    ```python
    turbo_stream.append("messages", "Message.jx", message=msg)
    turbo_stream.replace(post, component="posts/Post.jx", post=post)
    turbo_stream.remove("message_1")
    ```

    `replace` and `update` take `method="morph"` to morph the target instead
    of swapping it.

    `target` is an element id, or a model instance (its `dom_id` is used). Pass
    `targets` with a CSS selector instead to act on every matching element.

    In a template, the `stream` tag takes the action and the same
    arguments, and its body is the content:

    ```html+jinja
    {% stream "append", "messages" %}
      <li>{{ message.body }}</li>
    {% endstream %}
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
        method: str = "",
        **props: t.Any,
    ) -> Markup:
        return self._render(
            action,
            target=target,
            targets=targets,
            component=component,
            html=html,
            stream_method=method,
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

    def replace(
        self, target=None, component="", *, targets=None, html="", method="", **props
    ):
        """Replace the target element(s) entirely with the fragment.

        With `method="morph"`, the element is morphed into the fragment: only
        what differs is changed, so focus and scroll are kept.
        """
        return self._render(
            "replace",
            target=target,
            targets=targets,
            component=component,
            html=html,
            stream_method=method,
            **props,
        )

    def update(
        self, target=None, component="", *, targets=None, html="", method="", **props
    ):
        """Replace the inner content of the target element(s).

        With `method="morph"`, the content is morphed into the fragment: only
        what differs is changed, so focus and scroll are kept.
        """
        return self._render(
            "update",
            target=target,
            targets=targets,
            component=component,
            html=html,
            stream_method=method,
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

    def refresh(
        self, *, request_id: str = "", method: str = "", scroll: str = ""
    ) -> Markup:
        """Trigger a Turbo page refresh. Carries no target or fragment.

        Pass `request_id` to let the originating tab skip its own refresh.

        `method` (`"morph"` or `"replace"`) and `scroll` (`"preserve"` or
        `"reset"`) say how this refresh is applied, instead of the page's
        `turbo-refresh-method` and `turbo-refresh-scroll` meta tags.
        """
        attrs = {"request-id": request_id, "method": method, "scroll": scroll}
        html_attrs = "".join(
            f' {name}="{escape(value)}"' for name, value in attrs.items() if value
        )
        return Markup(f'<turbo-stream action="refresh"{html_attrs}></turbo-stream>')

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
        stream_method: str = "",
        **props: t.Any,
    ) -> Markup:
        if component:
            inner_html = current.app.catalog.render(component, **props)
        else:
            # `caller` renders the body of a template's `turbo_stream` tag.
            if caller:
                inner_html = caller()
            else:
                inner_html = html

        selector = self._selector(target, targets)
        inner = "" if action == "remove" else f"<template>{inner_html}</template>"
        method = f' method="{escape(stream_method)}"' if stream_method else ""
        return Markup(
            f'<turbo-stream action="{escape(action)}"{method} {selector}>{inner}</turbo-stream>'
        )

    @staticmethod
    def _selector(target: t.Any, targets: str | None) -> str:
        if targets is not None:
            return f'targets="{escape(targets)}"'
        if not isinstance(target, str):
            target = dom_id(target)
        return f'target="{escape(target)}"'


turbo_stream = TurboStream()
