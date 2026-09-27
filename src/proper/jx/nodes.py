"""
Jx | Copyright (c) Juan-Pablo Scaletti
"""

from dataclasses import dataclass, field

from .lexer import Attribute
from .span import Span


@dataclass(slots=True)
class Text:
    value: str
    span: Span


@dataclass(slots=True)
class Expr:
    """A `{{ … }}`, kept opaque: the lexer delimits it, nobody reads inside."""

    value: str
    span: Span


@dataclass(slots=True)
class Stmt:
    """A `{% … %}` that is not a Jx construct, kept opaque."""

    value: str
    keyword: str
    span: Span


@dataclass(slots=True)
class Comment:
    value: str
    span: Span


@dataclass(slots=True)
class Raw:
    value: str
    span: Span


@dataclass(slots=True)
class Slot:
    name: str
    span: Span
    default: list["Node"] = field(default_factory=list)
    # `{% slot a -%}` … `{%- endslot %}`: trim the default content.
    lstrip: bool = False
    rstrip: bool = False
    # `{%- slot a %}` … `{% endslot -%}`: trim the source around the whole
    # construct. The tags are replaced by generated ones, so these have to be
    # carried over by hand or Jinja never sees them.
    strip_before: bool = False
    strip_after: bool = False


@dataclass(slots=True)
class Fill:
    name: str
    span: Span
    body: list["Node"] = field(default_factory=list)
    lstrip: bool = False
    rstrip: bool = False


@dataclass(slots=True)
class Component:
    name: str
    span: Span
    attrs: tuple[Attribute, ...] = ()
    children: list["Node"] = field(default_factory=list)
    fills: list[Fill] = field(default_factory=list)


@dataclass(slots=True)
class Block:
    """
    A Jinja block (`{% if %}` … `{% endif %}`) whose body we do not interpret.

    It exists only so the tree knows a component cannot be opened inside it and
    closed outside; its own statements are emitted verbatim.
    """

    keyword: str
    open: Stmt
    span: Span
    children: list["Node"] = field(default_factory=list)
    close: Stmt | None = None


@dataclass(slots=True)
class Declaration:
    """
    A `{# def … #}`, `{# import … #}`, `{# css … #}` or `{# js … #}` from the
    component's header.

    The comment itself stays in `Document.children` and is emitted verbatim;
    this is the same text, split into keyword and payload, so a tool does not
    have to recognise the header on its own.

    `span` marks the opening `{#`; `expr_span` covers the payload, so an
    offset within the payload can be mapped back to a place in the file.
    """

    keyword: str
    expr: str
    span: Span
    expr_span: Span | None = None


@dataclass(slots=True)
class Document:
    children: list["Node"] = field(default_factory=list)
    declarations: list[Declaration] = field(default_factory=list)


Node = Text | Expr | Stmt | Comment | Raw | Slot | Fill | Component | Block


def walk(node) -> "list[Node]":
    """
    Yield every node in the tree, parents first.

    Sub-lists are visited in the order the emitter writes them out: a
    component's fills become macros declared *before* its call, so they come
    before its children. Slot order depends on this.
    """
    out: "list[Node]" = []

    def visit(current) -> None:
        out.append(current)
        if isinstance(current, Component):
            for child in current.fills:
                visit(child)
            for child in current.children:
                visit(child)
        elif isinstance(current, Fill):
            for child in current.body:
                visit(child)
        elif isinstance(current, Slot):
            for child in current.default:
                visit(child)
        elif isinstance(current, (Document, Block)):
            for child in current.children:
                visit(child)

    visit(node)
    return out
