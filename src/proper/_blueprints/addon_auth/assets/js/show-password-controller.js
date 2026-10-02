import { Controller } from "@hotwired/stimulus"

class ShowPasswordController extends Controller {
  static targets = ["input", "show", "hide"]

  show() {
    this.inputTarget.type = "text"
    this.showTarget.classList.add("hidden")
    this.hideTarget.classList.remove("hidden")
  }

  hide() {
    this.inputTarget.type = "password"
    this.hideTarget.classList.add("hidden")
    this.showTarget.classList.remove("hidden")
  }
}

window.Stimulus.register("show-password", ShowPasswordController)
