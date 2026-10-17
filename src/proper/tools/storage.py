from ..errors import ConfigError
from ..storage.imageops import MAX_PIXELS, SAFE_LOADERS, restrict_loaders, set_max_pixels


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
    # libvips image loaders allowed when generating variants. Every other
    # loader is blocked, so a malicious upload can't reach an unsafe loader
    # (the SVG loader reads local files, the ImageMagick delegate opens the
    # door to RCE, ...). Add a loader class prefix to enable more formats,
    # e.g. "VipsForeignLoadJxl" for JPEG-XL.
    "STORAGE_SAFE_IMAGE_LOADERS": SAFE_LOADERS,
    # The most pixels (width x height) of an image a variant is made from,
    # or `None` for no limit
    "STORAGE_MAX_IMAGE_PIXELS": MAX_PIXELS,
}


def setup(app):
    if not app.config.get("STORAGE"):
        return

    for name, value in DEFAULT_CONFIG.items():
        app.config.setdefault(name, value)
    validate_config(app.config)
    restrict_loaders(app.config["STORAGE_SAFE_IMAGE_LOADERS"])
    set_max_pixels(app.config["STORAGE_MAX_IMAGE_PIXELS"])


def validate_config(config):
    if not isinstance(config.get("STORAGES"), dict):
        raise ConfigError("STORAGES config must be a dictionary")
