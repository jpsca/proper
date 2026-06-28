from .concern import Concern


class FormValidation(Concern):
    """Provides `validate_form` for controllers that build a `self.form`.

    Register it in the controller's `before` list, after the callback
    that builds the form:

        before = [
            {"do": "set_post", "exclude": ["index", "new", "create"]},
            {"do": "set_form", "exclude": ["index", "show", "delete"]},
            {"do": "validate_form", "only": ["create", "update"]},
        ]
    """

    def validate_form(self):
        form = getattr(self, "form", None)
        if form and form.is_invalid:
            self.redo()
