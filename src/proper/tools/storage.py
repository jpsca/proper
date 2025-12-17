from ..errors import ConfigError
from ..storage import Storage


DEFAULT_CONFIG = {
    # The storage service to use for storing files. `None` to disable
    "STORAGE": "local",

    # Available storage services
    "STORAGE_SERVICES": {
        "local": {
            "type": "Disk",
            "root": "storage/",
        }
    },

    # Image content types that can be processed without being converted to
    # the fallback PNG format. If you want to use WebP or AVIF variants in
    # your application you can add image/webp or image/avif to this list
    "STORAGE_WEB_IMAGE_CONTENT_TYPES": (
        "image/png",
        "image/jpeg",
        "image/gif",
    ),

    # List of content types allowed to be served inline
    "STORAGE_ALLOWED_INLINE_CONTENT_TYPES": (
        "image/",
        "video/",
        "application/pdf",
    ),
}


def setup(app):
    if not app.config.get("STORAGE"):
        app.storage = None
        return

    for name, value in DEFAULT_CONFIG.items():
        app.config.setdefault(name, value)
    validate_config(app.config)

    app.storage = Storage(app)


def validate_config(config):
    if not isinstance(config.get("STORAGE_SERVICES"), dict):
        raise ConfigError("STORAGE_SERVICES config must be a dictionary")
