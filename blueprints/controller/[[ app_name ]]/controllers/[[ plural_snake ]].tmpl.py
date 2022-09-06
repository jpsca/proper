from proper import request, response  # noqa

from .app import AppController


class [[ plural_pascal ]](AppController):

    [%- for action in actions %]
    def [[ action ]](self):
        pass
    [% endfor -%]
