import * as Lexxy from "lexxy"


// Tell Lexxy to emit `<proper-attachment>` placeholder tags (instead of
// the default `<action-text-attachment>`) so the Python renderer can
// match on its own canonical name. The namespace bumps the content-type
// prefix on prompt/embed metadata from `actiontext` to `proper`.
//
// `Lexxy.configure` MUST run before Lexxy registers its custom elements
// (Lexxy defers registration to a `setTimeout(0)` after import, then
// reads this config to choose tag names). The import-time side effect
// here is what guarantees that ordering: this module is `{#js ...#}`-
// imported from `rich_text_editor.jx`, which runs before the editor
// mounts.
Lexxy.configure({
  global: {
    attachmentTagName: "proper-attachment",
    attachmentContentTypeNamespace: "proper",
  },
})


// NOTE — Turbo + Lexxy: the `connectedCallback` upgrade-order fix lives
// in `application.js`, NOT here. It must intercept
// `customElements.define` before Lexxy calls it, and this module loads
// lazily (only when the editor view is rendered). See
// `application.js` for the full rationale.


// Re-init on Turbo morph (Refresh Streams / morph-element).
//
// Turbo's morph algorithm preserves DOM identity rather than swapping
// the subtree. Lexxy's internal state (Lexical editor, extensions,
// listeners) doesn't survive being morphed in place. Removing and
// re-inserting fires `disconnectedCallback` + `connectedCallback`,
// letting Lexxy rebuild from the morphed attributes.
document.addEventListener("turbo:morph-element", (event) => {
  const target = event.target
  if (target.tagName !== "LEXXY-EDITOR") return
  const parent = target.parentElement
  if (!parent) return
  const nextSibling = target.nextSibling
  target.remove()
  if (nextSibling) parent.insertBefore(target, nextSibling)
  else parent.appendChild(target)
})
