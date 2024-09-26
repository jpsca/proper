,
    resource("[[ mount_point ]]", to=[[ singular_pascal ]]
    [%- if only %], only="[[ ",".join(only) ]]"
    [%- elif exclude %], exclude="[[ ",".join(exclude) ]]"[% endif %]
    [%- if singular %], singular=True[% endif -%]
    [%- if restore %], restore=True[% endif -%]
    ),
]
from .views.[[ view_snake ]] import [[ singular_pascal ]]
