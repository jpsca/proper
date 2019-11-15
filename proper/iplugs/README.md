## proper.iplugs

This “plugs” are function that take a request, a response, and an application instance.
They return nothing, all side-effects must be on the request and/or the response
instances.

The plugs in this folder are private and intended to be used by Proper internally.
For instance, even the URL matcher and controller dispatcher are implemented as plugs.

Unlike the public plugs in `proper.plugs` this functions are only called once
per request.
