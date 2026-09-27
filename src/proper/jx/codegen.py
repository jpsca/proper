"""
Jx | Copyright (c) Juan-Pablo Scaletti
"""

from jinja2 import nodes
from jinja2.compiler import CodeGenerator


SAFE_FILTER = "_jx_safe"


def jx_safe(value):
    """
    Identity. Registered so that `|_jx_safe` is a valid filter even when the
    environment is not using `JxCodeGenerator` — a user-supplied environment
    may carry its own generator. The marker then costs one call per output
    instead of being free, which is the same price as the `escape()` it was
    meant to replace, and the result is identical either way.
    """
    return value


def _is_marked(node) -> bool:
    return isinstance(node, nodes.Filter) and node.name == SAFE_FILTER


class JxCodeGenerator(CodeGenerator):
    """
    Emits `{{ x|_jx_safe }}` as a bare `yield x`.

    Jx generates a handful of output expressions whose value is always a
    `Markup`: a component call and a slot fill. Jinja does not know that, so it
    wraps each one in `escape()`, which asks the value for `__html__` and then
    builds a second `Markup` with the same characters — a string copy per
    component, per render.

    `|safe` does not help: it compiles to `escape(mark_safe(x))`, which adds a
    call rather than removing one. Skipping the wrapper is the only way to not
    pay for it, and that decision belongs at code generation time.

    Only expressions Jx itself emitted carry the marker. Anything written by
    hand in a component, including `{{ content }}` and `{{ attrs.render() }}`,
    goes through the normal escaping path.
    """

    def visit_Filter(self, node: nodes.Filter, frame) -> None:
        if node.name == SAFE_FILTER and node.node is not None:
            # The marker is not a transformation; render the value it wraps.
            self.visit(node.node, frame)
            return
        super().visit_Filter(node, frame)

    def _output_child_pre(self, node, frame, finalize) -> None:
        # A configured `finalize` has to run on every value, marked or not, so
        # that path keeps the wrapper it needs to be called from.
        if _is_marked(node) and finalize.src is None:
            return
        super()._output_child_pre(node, frame, finalize)

    def _output_child_post(self, node, frame, finalize) -> None:
        if _is_marked(node) and finalize.src is None:
            return
        super()._output_child_post(node, frame, finalize)
