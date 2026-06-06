from ..errors import ConfigError


DEFAULT_CONFIG = {
    # The storage service to use for storing files. `None` to disable
    "STORAGE": "local",
    # Available storage services
    "STORAGES": {
        "local": {
            "type": "Disk",
            "root": "storage/",
        }
    },
    # Image content types that can be processed without being converted to
    # the fallback PNG format. If you want to use WebP or AVIF variants in
    # your application you can add image/webp or image/avif to this list
    "STORAGE_ALLOWED_VARIANTS": (
        "image/png",
        "image/jpeg",
        "image/gif",
    ),
    # Format used for variants when the source content type isn't in
    # STORAGE_ALLOWED_VARIANTS (and the caller didn't pass save={"format": ...})
    "STORAGE_FALLBACK_FORMAT": "png",
    # Glob patterns of content types allowed to be served inline
    "STORAGE_ALLOWED_INLINE": (
        "image/*",
        "video/*",
        "application/pdf",
    ),
}


def setup(app):
    if not app.config.get("STORAGE"):
        return

    for name, value in DEFAULT_CONFIG.items():
        app.config.setdefault(name, value)
    validate_config(app.config)


def validate_config(config):
    if not isinstance(config.get("STORAGES"), dict):
        raise ConfigError("STORAGES config must be a dictionary")
