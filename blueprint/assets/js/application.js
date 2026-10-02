import { Application } from "@hotwired/stimulus"

window.Stimulus = Application.start()

/* Added so the DOMContentLoaded events work without any changes. */
document.addEventListener("turbo:load", function() {
  document.dispatchEvent(new CustomEvent("DOMContentLoaded"));
});


/* Wrap `<lexxy-editor>`'s `connectedCallback` BEFORE Lexxy calls
 * `customElements.define`.
 *
 * Per the WHATWG HTML spec, `customElements.define(name, ctor)`
 * captures the lifecycle callbacks (`connectedCallback`,
 * `disconnectedCallback`, etc.) from the prototype AT DEFINE TIME and
 * stores them in the element's custom element "definition". When the
 * browser fires reactions on element connection, it invokes those
 * cached references — NOT the current prototype. Patching
 * `Class.prototype.connectedCallback` AFTER define has no effect on
 * reactions; only explicit `el.connectedCallback()` calls see the
 * new version.
 *
 * The only way to patch effectively is to intercept
 * `customElements.define` itself and wrap the prototype's callback
 * BEFORE delegating to the real define, so the captured reference IS
 * the wrapped one. This must be installed before any Lexxy script
 * runs — `application.js` qualifies because it's part of the layout's
 * always-loaded JS, ahead of any view-scoped `{#js #}` import.
 *
 * Why we need this for Lexxy + Turbo: on Turbo Drive nav, the browser
 * upgrades inserted custom elements in document order — parent before
 * child. `<lexxy-editor>`'s `connectedCallback` synchronously looks
 * up its toolbar via `document.getElementById` and calls `setEditor`
 * on it, but the toolbar (a child element) hasn't been upgraded yet,
 * so its class methods don't exist. The wrapper calls
 * `customElements.upgrade(this)` first, which promotes every defined
 * custom element in the editor's subtree to its class, then runs the
 * original connect with `setEditor` available.
 */
const _originalDefine = customElements.define.bind(customElements);
customElements.define = function (name, ctor, options) {
  if (name === "lexxy-editor" && ctor?.prototype?.connectedCallback) {
    const originalConnect = ctor.prototype.connectedCallback;
    ctor.prototype.connectedCallback = function () {
      customElements.upgrade(this);
      return originalConnect.call(this);
    };
  }
  return _originalDefine(name, ctor, options);
};
