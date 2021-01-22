from datetime import timedelta


DEFAULT_CONFIG = {
    "debug": False,

    # Turn off to let debugging middleware handle exceptions.
    "catch_all_errors": True,

    # Limits the total content length (in bytes).
    # Raises a RequestEntityTooLarge exception if this value is exceeded.
    "max_content_length": 2 ** 23,  # 8 MB

    # Limits the content length (in bytes) of the query string.
    # Raises a RequestEntityTooLarge or an UriTooLong if this value is exceeded.
    "max_query_size": 2 ** 20,  # 1 MB

    # Session config
    "session": {
        "cookie_name": "_session",
        "cookie_domain": None,
        "cookie_path": "/",
        "cookie_httponly": True,
        "cookie_secure": False,
        "cookie_samesite": None,
        "lifetime": timedelta(days=30).total_seconds(),
    },

    # Static assets
    "static": {
        "host": None,

        # When set to False then compressed files will not be created but static files
        # will still get md5 tagged.
        "compress": True,
    }
}
