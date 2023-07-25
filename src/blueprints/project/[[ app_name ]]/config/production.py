from .app import config


config["debug"] = False
config["host"] = "https://YOUR-DOMAIN.com"
config["cookie"]["secure"] = True

# List of secret keys, **oldest to newest**.
# Every key in the list is valid, so you can periodically generate a new key
# and remove the oldest one to add and extra layer of mitigation
# against an attacker discovering a secret key
config["secret_keys"] = []  # IN CREDENTIALS
