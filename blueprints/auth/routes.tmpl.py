,

    get("sign-in", to=Auth.sign_in),
    post("sign-in", to=Auth.sign_in),
    post("sign-out", to=Auth.sign_out),
    scope("password")(
        get("reset", to=Auth.reset),
        post("reset", to=Auth.reset),
        get("reset/:token", to=Auth.reset_validate),
        get("change", to=Auth.password_change),
        post("change", to=Auth.password_change),
    ),
]

