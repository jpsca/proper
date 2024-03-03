import typing as t

from ..helpers.render import (
    BLUEPRINTS,
    BlueprintRender,
    add_dependencies,
    sort_imports,
)


if t.TYPE_CHECKING:
    from proper import App

FIRST_YAML = """
{locale}:
    hello: World

"""
I18N_BLUEPRINT = BLUEPRINTS / "i18n"
APPLICATION_VIEW = "views/app.py"
ENTRY_POINT = "\n    concerns = ["
INSERT = f"{ENTRY_POINT}\n        SetLocale,\n"

DEPENDENCIES = [
    "poyo",
]


def install(app: "App") -> None:
    """Install internationalization (i18n) support."""
    if not app.config.LOCALES_FOLDER:
        raise ValueError("The LOCALES_FOLDER config is not defined")

    app.locales_path.mkdir(exist_ok=True)
    first_locale = app.config.LOCALE_DEFAULT or "en"
    first_yaml = f"{first_locale}.yml"
    first_content = FIRST_YAML.format(locale=first_locale)
    (app.locales_path / first_yaml).write_text(first_content)

    bp = BlueprintRender(
        I18N_BLUEPRINT,
        app.root_path.parent,
        context={
            "app_name": app.root_path.name,
        },
    )
    bp()

    curr_appc = app.root_path / APPLICATION_VIEW
    code = sort_imports(curr_appc.read_text())
    if ENTRY_POINT in code:
        code = code.replace(ENTRY_POINT, INSERT, 1)
    curr_appc.write_text(code)

    add_dependencies(app.root_path, DEPENDENCIES)
