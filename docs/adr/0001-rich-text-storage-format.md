# ADR-0001: Store Rich Text as JSON, not HTML

**Status:** Accepted (2026-05-21)


## Context

The rich text addon stores user-composed bodies - articles, comments,
notes - with embedded images and other attachments. Two natural wire
formats:

- **HTML with custom elements**, the approach Rails' Action Text takes:
  the body is sanitized HTML containing `<action-text-attachment
  sgid="...">` markers, produced and consumed by the editor (Trix).
- **Structured JSON (a ProseMirror-style AST)**, the approach modern
  editors like TipTap, ProseMirror, and Lexical take natively.

The choice cascades. It determines what the editor produces, what the
renderer accepts, and what the trust boundary looks like for stored
content reaching a browser.


## Decision

Store the body as a ProseMirror-shaped JSON document.


## Consequences

- The renderer is **closed-world**: it dispatches over a known set of
  node types and emits HTML for each. An unknown node type renders as
  the empty string. There is no path for arbitrary stored HTML to
  reach the browser, so no HTML sanitizer is required.
- The framework's contract becomes the **JSON schema**, not a
  particular editor. TipTap is the default (vendored, bundled with the
  addon) but the user can swap it for ProseMirror directly, Lexical,
  or a custom editor - provided they emit a document the renderer
  understands.
- Storage is a single JSON column on the parent model. Pretty-printing
  the column gives a structured, diffable tree. The plain-text
  representation is derivable by walking the AST without parsing HTML.
- The renderer still has to be careful with URL schemes on `link`
  marks (allowlist `http`, `https`, `mailto`, `tel`) and HTML-escape
  text nodes. These are minimal - much smaller than the attack surface
  a sanitizer must cover.

Trade-offs accepted:

- The user can't open the body in any HTML editor (it's not HTML).
- Migrating to a different storage format later (e.g. Markdown) means
  walking the AST and emitting the target format - straightforward
  but non-trivial.


## Alternatives considered

- **HTML with custom elements (Action Text style).** Rejected because
  it commits us to an HTML sanitizer and to parsing HTML on every save
  *and* render. The single benefit - "anyone can open the body in any
  editor" - turns out to be largely false in practice because the
  embedded attachment markers are addon-specific.
- **Markdown.** Rejected because Markdown can't natively express
  embedded attachments with per-instance metadata (alt text, caption);
  any Markdown extension we'd invent would defeat the simplicity that
  attracts people to Markdown in the first place.
