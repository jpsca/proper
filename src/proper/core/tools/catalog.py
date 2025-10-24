import jx

from proper.cache import FragmentCacheExtension


def setup(app):
    jglobals = {
        "url_for": app.url_for,
        "url_is": app.url_is,
        "url_startswith": app.url_startswith,
    }
    jfilters = {}

    if app.i18n:
        jglobals["_"] = app.i18n
        jfilters.update({
            "format_datetime": app.i18n.format_datetime,
            "format_date": app.i18n.format_date,
            "format_time": app.i18n.format_time,
            "format_timedelta": app.i18n.format_timedelta,
            "format_skeleton": app.i18n.format_skeleton,
            "format_list": app.i18n.format_list,
            "format_decimal": app.i18n.format_decimal,
            "format_compact_decimal": app.i18n.format_compact_decimal,
            "format_currency": app.i18n.format_currency,
            "format_compact_currency": app.i18n.format_compact_currency,
            "format_percent": app.i18n.format_percent,
            "format_scientific": app.i18n.format_scientific,
        })

    app.catalog = jx.Catalog(
        app.views_path,
        auto_reload=app.config.DEBUG,
        filters=jfilters,
        extensions=[
            FragmentCacheExtension,
        ],
        **jglobals,
    )
    app.catalog.jinja_env.extend(app_cache=app.cache)
