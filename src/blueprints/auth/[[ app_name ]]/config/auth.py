from proper import DotDict


auth_config = DotDict()
auth_config.hash_name = "argon2"
auth_config.rounds = None  # default
auth_config.password_minlen = 9
auth_config.password_maxlen = 1024
auth_config.token_life = 10800  # 3 hours
