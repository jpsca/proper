/* Insert the CSRF header to every Turbo request.
This function fires before Turbo issues a network request
(to fetch a page, submit a form, preload a link, etc.).
*/
document.addEventListener("turbo:before-fetch-request", (event) => {
  if (event.detail.fetchOptions.method == "GET") return;
  event.preventDefault();
  event.detail.fetchOptions.headers["X-CSRF-Token"] = window.csrf_token;
  event.detail.resume();
});
