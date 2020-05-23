"""A base controller class, all other application controllers must
inherit from. Stores data available to view/template.
"""


class BaseController(object):

    _callbacks_before = tuple()
    _callbacks_after = tuple()

    def _dispatch(self, action, req, resp, app):
        run_callbacks(self._callbacks_before, req, resp, app)
        if resp.stop:
            return

        if not resp.dispatched:
            self._call(action, req, resp)

        run_callbacks(self._callbacks_after, req, resp, app)

    def _call(self, action, req, resp):
            method = getattr(self, action)

            # We call the endpoint but we do not expect a result value.
            # All the side effects of this call should be stored in the same
            # controller and in `resp`.
            method(req, resp, **req.matched_params)

            # If resp.body was manually set, our work here is done.
            if resp.has_body or resp.stop:
                return

            # Otherwise, it's render time...
            # `_render()` is a method all controllers MUST have implemented
            resp.body = self._render(req, resp)

    def _render(self, req, resp):
        """Placeholder to be implemented in the application.
        Should render the current template.

        A possible implementation could look like this:

        ```python
        def _render(self, req, resp):
            template = resp.template + resp.format
            return render(template, app=app, req=req, **self._as_dict())
        ```
        """
        raise NotImplementedError

    def _as_dict(self):
        """Serializable to a dictionary.
        """
        return {
            name: getattr(self, name)
            for name in dir(self)
            if not name.startswith("_")
        }


def run_callbacks(callbacks, req, resp, app):
    for callback in callbacks:
        if resp.stop:
            break
        callback(req, resp, app)
