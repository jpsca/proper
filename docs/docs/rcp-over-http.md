Nope, ignore this

# REST in peace

If you follow RESTful API design to the letter, you we´ll end creating or deleting "resources" when you really want to perform an action. For example: `POST /session` and `DELETE /session` for sign-in and sign-out, even if you are just creating or deleting a cookie. It's weird.

Instead, we recommend using an approach you could call "RCP over HTTP":

- Use REST-like URLs to GET resources, eg: `/products`, `/person/123`, `/posts/456/comments`, `/search?q=lorem+ipsum`, etc.
- Use specific action URLs, over POST, for everything else, eg: `/login`, `/cart/add-product`, `/users/123/delete`, `/my-data/csv-export`, `/comment/34/mark-as-spam`, etc.
- Ignore the HTTP verbs PUT, PATCH, and DELETE (OPTIONS is still useful for things like CORS and HEAD for HTTP caching).
