## proper.middleware

This functions that take a request, a response, and an application instance.
They return nothing, all side-effects must be on the request and/or the response instances.

The middleware functions in this folder are for private use.
For instance, even the URL matcher and controller dispatcher are implemented as middleware.
