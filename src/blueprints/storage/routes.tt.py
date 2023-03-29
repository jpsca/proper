,

    resource("storage", to=Storage, only="show", singular=True),
]
from .controllers import Storage
