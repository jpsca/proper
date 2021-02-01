
    [% for action in actions %]
    get("[[ action ]]", to="[[ pascal_name ]].index"),
    [%- endfor %]
]
