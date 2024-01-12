from .app import AppView


class [[ plural_pascal ]](AppView):

    [%- for action in actions %]
    def [[ action ]](self):
        pass
    [% endfor -%]
