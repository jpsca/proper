import typing as t

from proper.helpers import BLUEPRINTS
from proper.helpers.render import (
    add_dependencies,
    append_to_concerns,
    render_blueprint,
    sort_imports_in,
)


if t.TYPE_CHECKING:
    from proper.core.app import App


FIRST_YAML = """
{locale}:
    hello: World

"""
I18N_BLUEPRINT = BLUEPRINTS / "i18n"

SORT_IMPORTS_IN = [
    "controllers/base.py",
]

CONCERNS = ["SetLocale"]

DEPENDENCIES = [
    "babel",
    "poyo",
]


def install(app: "App") -> None:
    """Install internationalization and localization support."""
    app.locales_path.mkdir(exist_ok=True)
    first_locale = app.config.get("LOCALE_DEFAULT", "en")
    first_yaml = f"{first_locale}.yml"
    first_content = FIRST_YAML.format(locale=first_locale)
    (app.locales_path / first_yaml).write_text(first_content)

    render_blueprint(
        I18N_BLUEPRINT,
        app.root_path.parent,
        context={"app_name": app.name},
    )

    for filename in SORT_IMPORTS_IN:
        sort_imports_in(app.root_path / filename)

    appc = app.root_path / "controllers/base.py"
    append_to_concerns(appc, CONCERNS)

    add_dependencies(app.root_path, DEPENDENCIES)
