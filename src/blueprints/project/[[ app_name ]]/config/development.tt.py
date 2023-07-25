from .app import config


config["debug"] = True

config["secret_keys"] = [
    "---- This is a not-secret-secret_key just for development ----"
]

config["database"]["default"] = "sqlite"
