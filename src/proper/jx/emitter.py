"""
Jx | Copyright (c) Juan-Pablo Scaletti
"""

from .codegen import SAFE_FILTER
from .lexer import Attribute, AttrKind
from .nodes import (
    Block,
    Comment,
    Component,
    Document,
    Expr,
    Raw,
    Slot,
    Stmt,
    Text,
)


class JinjaEmitter:
    """
    Writes an AST back out as Jinja source.

    This is the only place that knows what the generated code looks like.
    Everything upstream deals in nodes, so a different backend means another
    class here, not another parser.
    """

    __slots__ = ("_fill_counter", "slots")

    def __init__(self) -> None:
        self._fill_counter = 0
        # Slot names in the order they are written out, deduplicated. Collected
        # here because emitting already walks the tree in that exact order.
        self.slots: dict[str, None] = {}

    def emit(self, document: Document) -> str:
        return self._nodes(document.children)

    # Private

    def _nodes(self, nodes: list) -> str:
        return "".join(self._node(node) for node in nodes)

    def _node(self, node) -> str:
        if isinstance(node, (Text, Expr, Comment, Raw, Stmt)):
            return node.value
        if isinstance(node, Block):
            close = node.close.value if node.close else ""
            return f"{node.open.value}{self._nodes(node.children)}{close}"
        if isinstance(node, Slot):
            return self._slot(node)
        if isinstance(node, Component):
            return self._component(node)
        raise TypeError(f"Cannot emit {type(node).__name__}")  # pragma: no cover

    def _slot(self, node: Slot) -> str:
        self.slots[node.name] = None
        default = self._strip(self._nodes(node.default), node.lstrip, node.rstrip)
        # `in` and not `.get()`: a fill that renders empty is still a fill, and
        # must win over the default.
        open_tag = "{%- if" if node.strip_before else "{% if"
        end_tag = "endif -%}" if node.strip_after else "endif %}"
        return (
            f"{open_tag} '{node.name}' in _slots %}}"
            f"{{{{ _slots['{node.name}']()|{SAFE_FILTER} }}}}"
            f"{{% else %}}{default}{{% {end_tag}"
        )

    def _component(self, node: Component) -> str:
        macros: list[str] = []
        args: list[str] = []

        if node.fills:
            refs = []
            for fill in node.fills:
                body = self._strip(self._nodes(fill.body), fill.lstrip, fill.rstrip)
                self._fill_counter += 1
                name = f"_jx_fill_{self._fill_counter}"
                macros.append(f"{{% macro {name}() %}}{body}{{% endmacro %}}")
                refs.append(f'"{fill.name}": {name}')
            args.append("_fills={" + ", ".join(refs) + "}")

        if node.attrs:
            pairs = [self._attr(attr) for attr in node.attrs]
            args.append("**{" + ", ".join(pairs) + "}")

        # The tag name travels as the first argument of a single call.
        # `_get(name).render(...)` would be two calls, and Jinja routes every
        # one of them through `Context.call`, which is not free.
        str_args = ", ".join([f'"{node.name}"', *args])

        content = self._nodes(node.children)
        if node.fills:
            # What is left between the fills is the default content; whitespace
            # around it is layout of the call site, not content.
            content = content.strip()

        if content:
            call = (
                f"{{% call _render({str_args}) -%}}"
                f"{content}"
                f"{{%- endcall %}}"
            )
        else:
            # No default content, so the component needs no `caller` at all.
            # `{% call %}` above yields its result directly, but a plain output
            # expression is wrapped in `escape()`, so this one says it is safe.
            call = f"{{{{ _render({str_args})|{SAFE_FILTER} }}}}"

        return f"{''.join(macros)}{call}"

    def _attr(self, attr: Attribute) -> str:
        # `-` is not valid in a Python keyword, so `data-foo` travels as
        # `data_foo`. `Attrs` turns it back into `data-foo` when rendering.
        name = attr.name.replace("-", "_")
        if attr.kind is AttrKind.FLAG:
            return f'"{name}":True'
        if attr.kind is AttrKind.EXPR:
            assert attr.value is not None
            return f'"{name}":{attr.value[2:-2].strip()}'
        return f'"{name}":{attr.value}'

    @staticmethod
    def _strip(body: str, lstrip: bool, rstrip: bool) -> str:
        if lstrip:
            body = body.lstrip()
        if rstrip:
            body = body.rstrip()
        return body
