/*
Add/Remove nested form rows dynamically.
Copyright © 2026 JPScaletti, MIT License

Usage:

```js
<div data-nestedform>

<!-- existing rows -->
  <div data-nestedform-target>
    <fieldset class="nestedform">
       ...
       <button data-nestedform-remove>Remove</button>
    </fieldset>
    ...
  </div>

  <!-- template of a new row -->
  <template data-nestedform-template>
    <fieldset class="nestedform">
      ...
      <button data-nestedform-remove>Remove</button>
    </fieldset>
  </template>

  <button data-nestedform-add>Add</button>
</div>
```
*/
const parser = new DOMParser();
const initialized = new WeakSet();

function initNestedForm(root) {
  if (initialized.has(root)) return;

  const target = root.querySelector('[data-nestedform-target]');
  const template = root.querySelector('[data-nestedform-template]');
  const wrapperSelector = root.dataset.wrapperSelector || ".nestedform";

  root.addEventListener("click", (e) => {
    const addBtn = e.target.closest("[data-nestedform-add]");
    if (addBtn) {
      e.preventDefault();

      const i = Date.now().toString().slice(4);
      const content = template.innerHTML.replace(/NEW_RECORD/g, i);

      const doc = parser.parseFromString(content, "text/html");
      const wrapper = doc.body.firstElementChild;
      wrapper.setAttribute("data-new", "true");

      wrapper.querySelectorAll("[id]").forEach((el) => {
        el.setAttribute("id", `${el.getAttribute("id")}_${i}`);
      });
      wrapper.querySelectorAll("[for]").forEach((el) => {
        el.setAttribute("for", `${el.getAttribute("for")}_${i}`);
      });

      target.appendChild(wrapper);
      root.dispatchEvent(new CustomEvent("nestedform:add", { bubbles: true }));
      return;
    }

    const removeBtn = e.target.closest("[data-nestedform-remove]");
    if (removeBtn) {
      e.preventDefault();

      const wrapper = removeBtn.closest(wrapperSelector);
      if (wrapper.dataset.newRecord) {
        wrapper.remove();
      } else {
        wrapper.style.display = "none";
        const input = wrapper.querySelector('input[name*="_destroy"]');
        if (input) input.value = "1";
      }

      root.dispatchEvent(new CustomEvent("nestedform:remove", { bubbles: true }));
    }
  });
  initialized.add(root);
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll("[data-nestedform]").forEach(initNestedForm);
});
