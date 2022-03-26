
config.auth = Dot()
config.auth.hash_name = "argon2"
config.auth.rounds = None  # default
config.auth.password_minlen = 9
config.auth.password_maxlen = 1024
config.auth.token_life = 10800  # 3 hours
