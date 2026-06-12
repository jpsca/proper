import { Controller } from "@hotwired/stimulus"

class ImageInputController extends Controller {
  static targets = ["input", "image", "filename", "destroyFlag"];
  static classes = ["hasImage", "dragging"];

  connect() {
    this.currentObjectUrl = null;
  }

  disconnect() {
    // Tear-down: revoke any blob URL we still own when the controller goes away
    this.#revokeUrl();
  }

  open(event) {
    // Don't reopen the picker when clicking inside the preview state,
    // and don't recurse from the synthetic input click.
    if (this.element.classList.contains(this.hasImageClass)) return;
    if (event.target === this.inputTarget) return;
    this.inputTarget.click();
  }

  fileSelected(event) {
    const file = event.target.files[0];
    if (file) this.#setFile(file);
  }

  drop(event) {
    // Always preventDefault so a stray drop never navigates the browser
    // away to the file. But only process the file when we're empty.
    event.preventDefault();
    this.element.classList.remove(this.draggingClass);
    if (this.element.classList.contains(this.hasImageClass)) return;
    const file = event.dataTransfer.files[0];
    if (file) this.#setFile(file);
  }

  dragEnter(event) {
    // Same idea: keep preventDefault on so drops are absorbed silently,
    // but only show the drag feedback when there's no image loaded.
    event.preventDefault();
    if (this.element.classList.contains(this.hasImageClass)) return;
    this.element.classList.add(this.draggingClass);
  }

  dragLeave(event) {
    event.preventDefault();
    this.element.classList.remove(this.draggingClass);
  }

  remove(event) {
    // Stop the click from bubbling to `open` on the root element
    event.stopPropagation();
    this.#clear();
  }

  // --- private helpers ---

  #setFile(file) {
    if (!file || !file.type.startsWith("image/")) return;

    this.#revokeUrl();
    this.currentObjectUrl = URL.createObjectURL(file);
    this.imageTarget.src = this.currentObjectUrl;
    this.imageTarget.alt = file.name;
    this.filenameTarget.textContent = `${file.name} · ${this.#formatSize(file.size)}`;
    this.element.classList.add(this.hasImageClass);
    // Replacement upload: the field's _original tracking will purge the
    // old attachment server-side. No explicit destroy signal needed.
    this.#setDestroyFlag(false);
  }

  #clear() {
    this.#revokeUrl();
    this.imageTarget.removeAttribute("src");
    this.imageTarget.alt = "";
    this.filenameTarget.textContent = "";
    this.inputTarget.value = "";
    this.element.classList.remove(this.hasImageClass);
    // No replacement: tell the server to destroy any existing attachment.
    this.#setDestroyFlag(true);
  }

  #setDestroyFlag(on) {
    if (this.hasDestroyFlagTarget) {
      this.destroyFlagTarget.value = on ? "1" : "0";
    }
  }

  #revokeUrl() {
    if (this.currentObjectUrl) {
      URL.revokeObjectURL(this.currentObjectUrl);
      this.currentObjectUrl = null;
    }
  }

  #formatSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }
}

window.Stimulus.register("image-input", ImageInputController);
