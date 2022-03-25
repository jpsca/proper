,
    resource("[[ controller_snake ]]", to=[[ controller_pascal ]]
    [%- if only %], only="[[ ",".join(only) ]]"
    [%- elif exclude %], exclude="[[ ",".join(exclude) ]]"[% endif %]
    [%- if singular %], singular=True[% endif -%]
    ),
]
