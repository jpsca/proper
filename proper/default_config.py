from datetime import timedelta


DEFAULT_CONFIG = {
    # Turn off to let debugging middleware handle exceptions.
    "catch_all_errors": True,
    # Limits the total content length (in bytes).
    # A RequestEntityTooLarge exception is raised if this value is exceeded.
    "max_content_length": 2 ** 23,  # 8 MB
    # Limits the content length (in bytes) of the form data, without files
    # or query string.
    # A RequestEntityTooLarge or an UriTooLong exception is raised if this value
    # is exceeded.
    "max_memory_size": 2 ** 20,  # 1 MB
    # 'host:port/root_path', used for `url_for(..., _external=True)`.
    "default_host": "0.0.0.0:3030",
    # The root path of the script, used for `url_for(..., _external=True)`.
    "root_path": "",
    # use 'https' instead of 'http' for `url_for(..., _external=True)`.
    # if a request isn't available.
    "use_ssl": False,
    # Session config
    "session": {
        "cookie_name": "_proper_session",
        "cookie_domain": None,
        "cookie_path": "/",
        "cookie_httponly": True,
        "cookie_secure": False,
        "cookie_samesite": None,
        "lifetime": timedelta(days=30).total_seconds(),
    },
}
