"""
## proper.base_controller

A base controller class, all other application controllers must
iherit from. Stores methods and data available to view/template.
"""


class BaseController(object):

    _pipeline = tuple()

    def _render(self, req, resp):
        raise NotImplementedError

    def _as_dict(self):
        """Serializable to a dictionary.
        """
        return {
            name: getattr(self, name)
            for name in dir(self)
            if not name.startswith("_")
        }
