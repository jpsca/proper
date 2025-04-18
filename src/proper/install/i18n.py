import typing as t

from proper.helpers.render import (
    BLUEPRINTS,
    BlueprintRender,
    add_dependencies,
    append_to_concerns,
    sort_imports_in,
)


if t.TYPE_CHECKING:
    from proper.core.app import App


FIRST_YAML = """
{locale}:
    hello: World

"""
I18N_BLUEPRINT = BLUEPRINTS / "i18n"
APPLICATION_CONTROLLER = "controllers/app.py"
CONCERNS = ["SetLocale"]

DEPENDENCIES = [
    "poyo",
]


def install(app: "App") -> None:
    """Install internationalization (i18n) support."""
    app.locales_path.mkdir(exist_ok=True)
    first_locale = app.config.LOCALE_DEFAULT or "en"
    first_yaml = f"{first_locale}.yml"
    first_content = FIRST_YAML.format(locale=first_locale)
    (app.locales_path / first_yaml).write_text(first_content)

    bp = BlueprintRender(
        I18N_BLUEPRINT,
        app.root_path.parent,
        context={},
    )
    bp()

    appc = app.root_path / APPLICATION_CONTROLLER
    sort_imports_in(appc)
    append_to_concerns(appc, CONCERNS)
    add_dependencies(app.root_path, DEPENDENCIES)
