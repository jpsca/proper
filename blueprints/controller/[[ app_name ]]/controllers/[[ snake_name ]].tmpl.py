from .application import ApplicationController


class [[ class_name|safe ]](ApplicationController):

    [%- for action in actions %]
    def [[ action|safe ]](self):
        pass
    [% endfor -%]
