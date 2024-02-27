,

    resource("storage", to=Storage, only="show", singular=True),
]
from .views.storage import Storage
