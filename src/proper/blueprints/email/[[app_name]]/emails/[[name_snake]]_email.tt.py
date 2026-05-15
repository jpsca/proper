from .base_email import BaseEmail


class [[name_pascal]]Email(BaseEmail):
    subject = ""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
