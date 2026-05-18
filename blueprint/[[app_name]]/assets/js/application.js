import { Application } from "@hotwired/stimulus"

window.Stimulus = Application.start()

/* Added so the DOMContentLoaded events work without any changes. */
document.addEventListener("turbo:load", function() {
  document.dispatchEvent(new CustomEvent("DOMContentLoaded"));
});