
## proper.callbacks

These “callbacks” are functions that take a request, a response, and an
application instance. They return nothing, all side-effects must be on the
request and/or the response instances.

A callback can be very simple, like `put_secure_headers` that set a few headers in all responses, or have a little more code, like `load_user` that load the current user from the
token in the cookie session/headers/etc.

The callbacks in this folder  are intended to be called in your application, by adding or removing them from the `_callbacks_before` and  `_callbacks_after` lists in your controllers:

```python
class ApplicationController(BaseController):

    _callbacks_before = [
        callbacks.LoadUser(user_by_id, session_key="_user_token"),
    ]
    _callbacks_after = [
        callbacks.put_secure_headers,
    ]

    # ...

class PrivateController(ApplicationController):

    _callbacks_before = [
        callbacks.LoadUser(user_by_id, session_key="_user_token"),
        callbacks.Protect(sign_in_url="/sign-in"),
    ]
```