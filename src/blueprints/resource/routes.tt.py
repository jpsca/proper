,
    resource("[[ view_snake ]]", to=[[ view_pascal ]]
    [%- if only %], only="[[ ",".join(only) ]]"
    [%- elif exclude %], exclude="[[ ",".join(exclude) ]]"[% endif %]
    [%- if singular %], singular=True[% endif -%]
    ),
]
from .views import [[ view_pascal ]]
