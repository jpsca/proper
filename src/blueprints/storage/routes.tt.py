,

    resource("storage", to=Storage, only="show", singular=True),
]
from .views import Storage
