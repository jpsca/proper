import { Controller } from "@hotwired/stimulus"

class FileInputController extends Controller {
  static targets = ["input", "filename", "destroyFlag"];
  static classes = ["hasFile", "dragging"];

  open(event) {
    // Don't reopen the picker when clicking inside the selected state,
    // and don't recurse from the synthetic input click.
    if (this.element.classList.contains(this.hasFileClass)) return;
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
    if (this.element.classList.contains(this.hasFileClass)) return;
    const file = event.dataTransfer.files[0];
    if (file) {
      // The native input doesn't receive drag-and-drop files, so we
      // assign the DataTransfer's FileList directly to keep form submit working.
      this.inputTarget.files = event.dataTransfer.files;
      this.#setFile(file);
    }
  }

  dragEnter(event) {
    event.preventDefault();
    if (this.element.classList.contains(this.hasFileClass)) return;
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
    this.filenameTarget.textContent = `${file.name} · ${this.#formatSize(file.size)}`;
    this.element.classList.add(this.hasFileClass);
    // Replacement upload: the field's _original tracking will purge the
    // old attachment. No explicit destroy signal needed.
    this.#setDestroyFlag(false);
  }

  #clear() {
    this.filenameTarget.textContent = "";
    this.inputTarget.value = "";
    this.element.classList.remove(this.hasFileClass);
    // No replacement: tell the server to destroy any existing attachment.
    this.#setDestroyFlag(true);
  }

  #setDestroyFlag(on) {
    if (this.hasDestroyFlagTarget) {
      this.destroyFlagTarget.value = on ? "1" : "0";
    }
  }

  #formatSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }
}

window.Stimulus.register("file-input", FileInputController);
