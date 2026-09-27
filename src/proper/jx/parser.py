"""
Jx | Copyright (c) Juan-Pablo Scaletti
"""

from .emitter import JinjaEmitter
from .exceptions import TemplateSyntaxError
from .lexer import Lexer, Token, TokenType, scan_header
from .nodes import (
    Block,
    Comment,
    Component,
    Declaration,
    Document,
    Expr,
    Fill,
    Raw,
    Slot,
    Stmt,
    Text,
)
from .span import Span


SLOT_NAME_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.:$-"
)

# Jinja block tags we can pair up. Anything else — including block tags added by
# a user extension — passes through as an opaque statement, exactly as before.
BLOCK_KEYWORDS = frozenset({
    "apply",
    "autoescape",
    "block",
    "call",
    "embed",
    "filter",
    "for",
    "if",
    "macro",
    "trans",
    "with",
})
END_KEYWORDS = {f"end{keyword}": keyword for keyword in (*BLOCK_KEYWORDS, "set")}

# Which list on a container its children go into.
CHILD_ATTR = {
    Document: "children",
    Component: "children",
    Block: "children",
    Slot: "default",
    Fill: "body",
}


class JxParser:
    def __init__(
        self,
        *,
        name: str,
        source: str,
        components: list[str],
    ):
        """
        Parses a template into an AST and writes it back out as Jinja source,
        with TitleCased HTML tags replaced by their component calls.

        Only the names in `components` are allowed as tags.

        Arguments:
            name:
                The name of the template for error reporting.
            source:
                The source code of the template.
            components:
                A list of allowed component names.

        """
        self.name = name
        self.source = source
        self.components = components
        self.lexer = Lexer(name, source)

    def parse(self, *, validate_tags: bool = True) -> tuple[str, tuple[str, ...]]:
        """
        Parses the template source code.

        Arguments:
            validate_tags:
                Whether to raise an error for unknown TitleCased tags.

        Returns:
            - The transformed template source code
            - The list of slot names.

        Raises:
            TemplateSyntaxError:
                If the template contains unknown components or syntax errors.

        """
        document = self.parse_ast(validate_tags=validate_tags)
        emitter = JinjaEmitter()
        source = emitter.emit(document)
        return source, tuple(emitter.slots)

    def parse_ast(self, *, validate_tags: bool = True) -> Document:
        """
        Parses the template source code into a tree.

        The tree is the parser's real output; `parse` is that tree written back
        out as Jinja. Tools that need to inspect a template — the CLI checker,
        an editor extension — should use this instead of matching patterns
        against the source.
        """
        document = Document(
            declarations=[
                Declaration(
                    keyword,
                    expr,
                    self.lexer.map.span(offset, offset),
                    self.lexer.map.span(expr_offset, expr_offset + len(expr)),
                )
                for keyword, expr, offset, expr_offset in scan_header(self.source)
            ]
        )
        stack: list = [document]

        for token in self.lexer.tokens():
            kind = token.type

            if kind is TokenType.TEXT:
                self._add(stack, Text(token.value, token.span))
            elif kind is TokenType.EXPR:
                self._add(stack, Expr(token.value, token.span))
            elif kind is TokenType.COMMENT:
                self._add(stack, Comment(token.value, token.span))
            elif kind is TokenType.RAW:
                self._add(stack, Raw(token.value, token.span))
            elif kind is TokenType.TAG_OPEN:
                self._open_tag(stack, token, validate_tags=validate_tags)
            elif kind is TokenType.TAG_CLOSE:
                self._close_tag(stack, token)
            else:
                self._statement(stack, token)

        self._check_unclosed(stack)
        return document

    # Private

    def _error(self, span: Span, message: str) -> TemplateSyntaxError:
        return TemplateSyntaxError.at(self.name, span, message)

    @staticmethod
    def _add(stack: list, node) -> None:
        container = stack[-1]
        getattr(container, CHILD_ATTR[type(container)]).append(node)

    def _open_tag(self, stack: list, token: Token, *, validate_tags: bool) -> None:
        if validate_tags and token.name not in self.components:
            raise self._error(token.span, f"Unknown component `{token.name}`")

        node = Component(name=token.name, attrs=token.attrs, span=token.span)
        self._add(stack, node)
        if not token.self_closing:
            stack.append(node)

    def _close_tag(self, stack: list, token: Token) -> None:
        top = stack[-1]
        if isinstance(top, Component) and top.name == token.name:
            stack.pop()
            return

        open_tag = next(
            (
                item
                for item in reversed(stack)
                if isinstance(item, Component) and item.name == token.name
            ),
            None,
        )
        if open_tag is None:
            # Nothing of that name is open, so there is nothing to close.
            if isinstance(top, Component):
                raise self._error(
                    token.span,
                    f"Unexpected `</{token.name}>`, "
                    f"the open component is `{top.name}`",
                )
            raise self._error(
                token.span,
                f"Unexpected `</{token.name}>`, no component is open",
            )

        # The tag does match something, but not the innermost open thing. What
        # is in the way is the actual mistake, so report that.
        if isinstance(top, (Slot, Fill)):
            keyword = "slot" if isinstance(top, Slot) else "fill"
            raise self._error(top.span, f"Unclosed `{{% {keyword} {top.name} %}}`")
        if isinstance(top, Component):
            raise self._error(top.span, f"Unclosed component `{top.name}`")
        raise self._error(
            open_tag.span,
            f"`{token.name}` is closed outside the block it was opened in",
        )

    def _statement(self, stack: list, token: Token) -> None:
        keyword = token.name
        stmt = Stmt(token.value, keyword, token.span)

        if keyword == "slot":
            node = Slot(
                name=self._construct_name(token),
                span=token.span,
                lstrip=token.rstrip,
                strip_before=token.lstrip,
            )
            self._add(stack, node)
            stack.append(node)
            return

        if keyword == "fill":
            container = stack[-1]
            if not isinstance(container, Component):
                raise self._error(
                    token.span,
                    "`{% fill %}` must be directly inside a component tag",
                )
            fill = Fill(
                name=self._construct_name(token),
                span=token.span,
                lstrip=token.rstrip,
            )
            # Fills are not content: they hang off the component itself, so the
            # emitter can turn each one into its own macro.
            container.fills.append(fill)
            stack.append(fill)
            return

        if keyword in ("endslot", "endfill"):
            expected = Slot if keyword == "endslot" else Fill
            top = stack[-1]
            if not isinstance(top, expected):
                raise self._error(token.span, f"Unexpected `{{% {keyword} %}}`")
            self._check_tail(token, self._after_keyword(token), keyword)
            top.rstrip = token.lstrip
            if isinstance(top, Slot):
                top.strip_after = token.rstrip
            stack.pop()
            return

        if keyword in BLOCK_KEYWORDS or (keyword == "set" and "=" not in token.value):
            node = Block(keyword=keyword, open=stmt, span=token.span)
            self._add(stack, node)
            stack.append(node)
            return

        if keyword in END_KEYWORDS:
            opened = END_KEYWORDS[keyword]
            top = stack[-1]
            if isinstance(top, Block) and top.keyword == opened:
                top.close = stmt
                stack.pop()
                return
            if isinstance(top, Component):
                raise self._error(
                    top.span,
                    f"`{top.name}` is not closed inside the "
                    f"`{{% {opened} %}}` block it was opened in",
                )
            raise self._error(token.span, f"Unexpected `{{% {keyword} %}}`")

        self._add(stack, stmt)

    @staticmethod
    def _after_keyword(token: Token) -> int:
        return token.value.index(token.name) + len(token.name)

    @staticmethod
    def _tail(token: Token, index: int) -> str:
        """
        Whatever a `{% … %}` still says after `index`, minus its closing `%}`.

        Both whitespace-control markers may sit in front of that `%}`, and
        neither of them is trailing text.
        """
        rest = token.value[index:].strip()
        rest = rest[:-3] if rest[-3:] in ("-%}", "+%}") else rest[:-2]
        return rest.strip()

    def _check_tail(self, token: Token, index: int, wrote: str) -> None:
        """These tags take what they take. Anything more is a typo, and a typo
        that is silently dropped from the output is worse than an error."""
        tail = self._tail(token, index)
        if tail:
            raise self._error(
                token.span, f"Unexpected `{tail}` after `{{% {wrote} %}}`"
            )

    def _construct_name(self, token: Token) -> str:
        """Read the name out of a `{% slot x %}` or `{% fill x %}`."""
        text = token.value
        index = self._after_keyword(token)
        # The keyword has to be separated from the name, or `{% slot-header %}`
        # reads as a slot named `-header` instead of the typo it is.
        if index < len(text) and text[index] not in " \t\r\n":
            raise self._error(token.span, f"`{{% {token.name} %}}` needs a name")
        while index < len(text) and text[index] in " \t\r\n":
            index += 1
        start = index
        while index < len(text) and text[index] in SLOT_NAME_CHARS:
            index += 1
        name = text[start:index]
        if not name:
            raise self._error(token.span, f"`{{% {token.name} %}}` needs a name")

        self._check_tail(token, index, f"{token.name} {name}")
        return name

    def _check_unclosed(self, stack: list) -> None:
        if len(stack) == 1:
            return
        node = stack[-1]
        if isinstance(node, Component):
            raise self._error(node.span, f"Unclosed component `{node.name}`")
        if isinstance(node, Slot):
            raise self._error(node.span, f"Unclosed `{{% slot {node.name} %}}`")
        if isinstance(node, Fill):
            raise self._error(node.span, f"Unclosed `{{% fill {node.name} %}}`")
        raise self._error(node.span, f"Unclosed `{{% {node.keyword} %}}`")


def parse_ast(
    source: str,
    *,
    name: str = "<string>",
    components: list[str] | None = None,
) -> Document:
    """
    Parse a template into a tree, without generating any Jinja code.

    Use this to inspect a template instead of matching patterns against its
    source: the tree knows what is a component, what is inside a comment or a
    `{% raw %}` block, and where each node starts.

    Arguments:
        source:
            The template source code.
        name:
            Name used in error messages.
        components:
            Allowed component names. When given, an unknown TitleCased tag is
            an error; when omitted, any tag is accepted.

    """
    parser = JxParser(name=name, source=source, components=components or [])
    return parser.parse_ast(validate_tags=components is not None)
