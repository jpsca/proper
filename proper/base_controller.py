"""A base controller class, all other application controllers must
inherit from. Stores data available to view/template.
"""


class BaseController(object):

    _before_action = tuple()
    _after_action = tuple()

    def _dispatch(self, action, req, resp, app):
        apply_filters(self._before_action, req, resp, app)
        if resp.stop:
            return

        if not resp.dispatched:
            self._call(action, req, resp)

        apply_filters(self._after_action, req, resp, app)

    def _call(self, action, req, resp):
        # We call the endpoint but we do not expect a result value.
        # All the side effects of this call should be stored in the same
        # controller and in `resp`.
        method = getattr(self, action)
        method(req, resp, **req.matched_params)

        if not resp.has_body and not resp.stop:
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


def apply_filters(filters, req, resp, app):
    for func in filters:
        if resp.stop:
            break
        func(req, resp, app)
