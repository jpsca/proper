from [[app_name]].router import router
from .app import AppController


@router.resource("[[ plural_snake ]]")
class [[ plural_pascal ]](AppController):

    [%- for action in actions %]
    def [[ action ]](self):
        pass
    [% endfor -%]
