,

    get("sign-in", to=Session.new),
    post("sign-in", to=Session.create),
    delete("sign-out", to=Session.delete),
    resource("password-reset", to=PasswordResets, exclude="index,show,delete"),
]
from .views.password import PasswordResets
from .views.session import Session
