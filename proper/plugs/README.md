
## proper.plugs

A “plug” is function that take a request, a response, and an application instance.
They return nothing, all side-effects must be on the request and/or the response
instances.

In a typical request, a plug is called twice: before and after a controller is called,
so it must be designed arround that fact.

A plug can be very simple, like `put_secure_headers` that set a few headers in all responses, or have a little more code, like `protect_from_forgery` that generates and verify a token against “Cross-Site Request Forgery” attacks.

The plugs in this folder  are intended to be called in your application, by adding or removing them from the `pipeline` lists in your routing scopes:

```
from proper import plugs, scope, get


browser = [
    plugs.session,
    plugs.protect_from_forgery,
    plugs.put_secure_headers,
]

routes = [
    scope('/', pipeline=browser)(
        get('', to='Pages.index'),
        ...
    )
]
```
