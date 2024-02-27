,
[% for action in actions %]
    get("[[ plural_snake ]]/[[ action ]]", to=[[ plural_pascal ]].[[ action ]]),[% endfor %]
]
from .views.[[ plural_snake ]] import [[ plural_pascal ]]
