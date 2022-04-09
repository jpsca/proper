from proper import Dot


config = auth_config = Dot()
config.hash_name = "argon2"
config.rounds = None  # default
config.password_minlen = 9
config.password_maxlen = 1024
config.token_life = 10800  # 3 hours
