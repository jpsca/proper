from .application import ApplicationController


class [[ class_name ]](ApplicationController):

    [%- for action in actions %]
    def [[ action ]](self):
        pass
    [% endfor -%]
