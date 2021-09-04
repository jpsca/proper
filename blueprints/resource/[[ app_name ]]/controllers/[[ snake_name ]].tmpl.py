from .application import ApplicationController


class [[ class_name|safe ]](ApplicationController):
    [%- for action in actions %]
    [% if action in ["index", "new", "create"] -%]
    def [[ action ]](self):
        pass
    [%- else -%]
    def [[ action ]](self[% if not singular %], uid[% endif %]):
        pass
    [%- endif %]

    [% endfor -%]
