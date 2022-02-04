from .application import ApplicationController


class [[ plural_pascal ]](ApplicationController):

    [%- for action in actions %]
    def [[ action ]](self):
        pass
    [% endfor -%]
