"""
## proper.base_controller

A base controller class, all other application controllers must
iherit from. Stores methods and data available to view/template.
"""


class BaseController(object):

    template = None

    def _asdict(self):
        """Serializable to a dictionary.
        """
        exclude = ("template",)
        return {
            name: getattr(self, name)
            for name in dir(self)
            if not name.startswith("_") and name not in exclude
        }

    def render(self):
        raise NotImplementedError
