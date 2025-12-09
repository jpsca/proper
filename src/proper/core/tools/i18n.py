from proper.i18n import I18n


DEFAULT_CONFIG = {
    "LOCALE_DEFAULT": "en",
    "TIMEZONE_DEFAULT": "UTC",
}

def setup(app):
    app.i18n = None

    if not app.locales_path.is_dir():
        return

    for name, value in DEFAULT_CONFIG.items():
        app.config.setdefault(name, value)

    app.i18n = I18n(
        app.locales_path,
        default_locale=app.config.LOCALE_DEFAULT,
        default_timezone=app.config.TIMEZONE_DEFAULT,
    )
