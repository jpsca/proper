,
[% for action in actions %]
    get("[[ snake_name ]]/[[ action ]]", to=[[ class_name ]].[[ action ]]),[% endfor %]
]

