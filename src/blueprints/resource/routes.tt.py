,
    resource("[[ mount_point ]]", to=[[ view_pascal ]]
    [%- if only %], only="[[ ",".join(only) ]]"
    [%- elif exclude %], exclude="[[ ",".join(exclude) ]]"[% endif %]
    [%- if singular %], singular=True[% endif -%]
    [%- if restore %], restore=True[% endif -%]
    ),
]
from .views.[[ view_snake ]] import [[ view_pascal ]]
