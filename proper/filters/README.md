## proper.filters

These “filters” are functions that take a request, a response, and an
application instance. They return nothing, all side-effects must be on the
request and/or the response instances.

A filter can be very simple, like `put_secure_headers` that set a few headers in all responses, or have a little more code, like `load_user` that load the current user from the
token in the cookie session/headers/etc.

The filters in this folder  are intended to be called in your application, by adding or removing them from the `_before_action` and  `_after_action` lists in your controllers:

```python
class ApplicationController(BaseController):

    _before_action = [
        filters.LoadUser(user_by_id, session_key="_user_token"),
    ]
    _after_action = [
        filters.put_secure_headers,
    ]

    # ...

class PrivateController(ApplicationController):

    _before_action = [
        filters.LoadUser(user_by_id, session_key="_user_token"),
        filters.Protect(sign_in_url="/sign-in"),
    ]
```