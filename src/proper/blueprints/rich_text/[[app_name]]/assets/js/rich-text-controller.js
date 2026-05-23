import { Controller } from "@hotwired/stimulus"
import * as Lexxy from "lexxy"


// Tell Lexxy to emit `<proper-attachment>` placeholder tags (instead of
// the default `<action-text-attachment>`) so the Python side can match
// on its own canonical name. The namespace bumps the content-type
// prefix on prompt/embed metadata from `actiontext` to `proper`.
//
// `Lexxy.configure` MUST run before the `<lexxy-editor>` custom element
// is constructed — Lexxy registers the element during the import call
// stack and reads config eagerly. Putting it right next to the import
// is the documented pattern.
Lexxy.configure({
  global: {
    attachmentTagName: "proper-attachment",
    attachmentContentTypeNamespace: "proper",
  },
})


// Bridges Lexxy's drag/drop/paste/picker into the Proper uploads endpoint.
//
// We don't set `data-direct-upload-url` on the `<lexxy-editor>` because
// that triggers Lexxy's built-in `@rails/activestorage` DirectUpload flow.
// Instead we hook `lexxy:file-accept` (cancelable) — when we
// `preventDefault()` Lexxy treats the file as rejected, then we insert a
// pending attachment ourselves and drive the upload via the endpoint.
class RichTextController extends Controller {
  static values = { uploadUrl: String }
  static targets = ["editor"]

  connect() {
    this.editor = this.editorTarget
    this.boundOnFileAccept = (event) => this.onFileAccept(event)
    this.editor.addEventListener("lexxy:file-accept", this.boundOnFileAccept)
  }

  disconnect() {
    if (this.editor && this.boundOnFileAccept) {
      this.editor.removeEventListener("lexxy:file-accept", this.boundOnFileAccept)
    }
  }

  onFileAccept(event) {
    const file = event.detail?.file
    if (!file) return

    // Reject from Lexxy's POV; we'll handle the upload ourselves.
    event.preventDefault()

    const pending = this.editor.contents.insertPendingAttachment(file)
    if (!pending) return

    this.#upload(file).then(
      (blob) => pending.setAttributes(blob),
      (err) => {
        console.error("rich-text upload failed:", err)
        pending.remove()
      },
    )
  }

  async #upload(file) {
    const body = new FormData()
    body.append("file", file)

    const headers = {}
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content
    if (csrf) headers["X-CSRF-Token"] = csrf

    const response = await fetch(this.uploadUrlValue, { method: "POST", body, headers })
    if (!response.ok) {
      throw new Error(`upload failed: ${response.status} ${response.statusText}`)
    }
    const data = await response.json()

    // Build the blob-shaped object Lexxy expects (mirrors ActiveStorage's
    // Blob).
    //
    // - `attachable_sgid`: serialized by Lexxy as the `sgid` attribute on
    //   `<proper-attachment>`. The Python renderer uses it to look the row
    //   up at render time, so we want the raw, stable Attachment UUID.
    // - `signed_id`: substituted by Lexxy into the editor's
    //   `blob-url-template` to compute the in-editor preview URL for
    //   non-previewable embeds. Must be a token the storage endpoint can
    //   resolve — the server sends one shaped exactly for that.
    return {
      attachable_sgid: data.id,
      signed_id: data.signed_id,
      filename: data.filename ?? file.name,
      content_type: data.content_type ?? file.type,
      byte_size: data.byte_size ?? file.size,
      previewable: data.previewable ?? false,
      url: data.url,
    }
  }
}


window.Stimulus.register("rich-text", RichTextController)
