from ..i18n import I18n


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

    app.i18n = i18n = I18n(
        app.locales_path,
        default_locale=app.config.LOCALE_DEFAULT,
        default_timezone=app.config.TIMEZONE_DEFAULT,
    )

    app.catalog.jinja_env.globals["_"] = i18n
    app.catalog.jinja_env.filters.update({
        "format_datetime": i18n.format_datetime,
        "format_date": i18n.format_date,
        "format_time": i18n.format_time,
        "format_timedelta": i18n.format_timedelta,
        "format_skeleton": i18n.format_skeleton,
        "format_list": i18n.format_list,
        "format_decimal": i18n.format_decimal,
        "format_compact_decimal": i18n.format_compact_decimal,
        "format_currency": i18n.format_currency,
        "format_compact_currency": i18n.format_compact_currency,
        "format_percent": i18n.format_percent,
        "format_scientific": i18n.format_scientific,
    })
