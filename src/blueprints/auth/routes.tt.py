,

    get("sign-in", to=Session.new),
    post("sign-in", to=Session.create),
    delete("sign-out", to=Session.delete),
    resource("password-reset", to=PasswordReset, exclude="index,show,delete"),
]
from .views.password import PasswordReset
from .views.session import Session
