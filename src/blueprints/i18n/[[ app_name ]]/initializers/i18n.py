from ..app import app


if app.catalog and app.i18n:
    app.catalog.jinja_env.globals["_"] = app.i18n.translate
