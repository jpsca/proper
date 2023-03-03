,
[% for action in actions %]
    get("[[ plural_snake ]]/[[ action ]]", to=[[ plural_pascal ]].[[ action ]]),[% endfor %]
]
from .controllers import [[ plural_pascal ]]
