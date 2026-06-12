import typing as t

from markupsafe import Markup, escape

from .global_context import current


def turbo_stream(
    action: str,
    target: str,
    component: str = "",
    *,
    html: str | Markup = "",
    **props: t.Any,
) -> Markup:
    """Wrap a rendered Jx `component` (or raw `html`) as a `<turbo-stream>`.

    Turbo applies the fragment to the element with id `target` using `action`, one of:

    - `append`,
    - `prepend`,
    - `replace`,
    - `update`,
    - `remove`,
    - `before`,
    - `after`, or
    - `morph`.

    Pass a `component` name with its props to render it through the catalog,
    or pass ready-made `html` directly.

    Broadcast the result over a stream for a live update, or return it from a
    controller as a `text/vnd.turbo-stream.html` response - the same fragment
    serves both. Concatenate several to send more than one operation at once.
    """
    if not html and component:
        html = current.app.catalog.render(component, **props)

    inner = "" if action == "remove" else f"<template>{html}</template>"
    return Markup(
        f'<turbo-stream action="{escape(action)}" target="{escape(target)}">'
        f"{inner}</turbo-stream>"
    )
