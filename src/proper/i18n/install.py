import typing as t

from ..helpers.render import (
    BLUEPRINTS,
    BlueprintRender,
    call,
    sort_imports,
)

if t.TYPE_CHECKING:
    from proper import App


I18N_BLUEPRINT = BLUEPRINTS / "i18n"
APPLICATION_VIEW = "views/app.py"
ENTRY_POINT = "\n    middleware = ["
INSERT = f"{ENTRY_POINT}\n        SetLocale,\n"

DEPENDENCIES = [
    "poyo",
]


def install(app: "App") -> None:
    """Install internationalization (i18n) support.
    """
    if not app.config.LOCALES_FOLDER:
        raise ValueError("The LOCALES_FOLDER config is not defined")

    app.locales_path.mkdir(exist_ok=True)
    first_yaml = f"{app.config.LOCALE_DEFAULT or 'en'}.yml"
    (app.locales_path / first_yaml).touch()

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

    for dep_name in DEPENDENCIES:
        call(f"poetry add {dep_name}")
