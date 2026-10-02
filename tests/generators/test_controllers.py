import re

import pytest

from proper.generators.controller import ACTIONS, gen_controller


# --- Fixtures ---

APP_NAME = "myapp"


@pytest.fixture()
def app_in_tmp(tmp_path, app):
    """A temporary app root with the directories the controller generator
    touches (controllers/, forms/, views/, models/)."""
    app_root = tmp_path / APP_NAME
    for d in ("models", "controllers", "forms", "views"):
        (app_root / d).mkdir(parents=True)
    (app_root / "controllers" / "__init__.py").write_text("")

    app.root_path = app_root
    app.name = APP_NAME
    return app


# --- Helpers ---


def _controllers(app):
    return app.root_path / "controllers"


def _closure_text(app):
    return (_controllers(app) / "card" / "closure_controller.py").read_text()


def _concern_text(app):
    return (_controllers(app) / "concerns" / "card_scoped.py").read_text()


def _init_text(app):
    return (_controllers(app) / "__init__.py").read_text()


def _test_text(app, child_snake):
    return (app.root_path.parent / "tests" / "controllers" / f"test_{child_snake}.py").read_text()


# --- A nested state-change controller ---


class TestStateChangeFiles:
    def test_creates_controller_in_parent_subfolder(self, app_in_tmp):
        gen_controller(app_in_tmp, "card/closure")
        assert (_controllers(app_in_tmp) / "card" / "closure_controller.py").exists()
        assert (_controllers(app_in_tmp) / "card" / "__init__.py").exists()

    def test_creates_scoped_concern(self, app_in_tmp):
        gen_controller(app_in_tmp, "card/closure")
        assert (_controllers(app_in_tmp) / "concerns" / "card_scoped.py").exists()
        assert (_controllers(app_in_tmp) / "concerns" / "__init__.py").exists()

    def test_creates_test_stub(self, app_in_tmp):
        gen_controller(app_in_tmp, "card/closure")
        assert (app_in_tmp.root_path.parent / "tests" / "controllers" / "test_closure.py").exists()

    def test_no_form_or_views(self, app_in_tmp):
        gen_controller(app_in_tmp, "card/closure")
        assert not (app_in_tmp.root_path / "forms" / "card").exists()
        assert not (app_in_tmp.root_path / "forms" / "closure.py").exists()
        assert not (app_in_tmp.root_path / "views" / "card").exists()
        assert not (app_in_tmp.root_path / "views" / "closure").exists()

    def test_wires_root_init(self, app_in_tmp):
        gen_controller(app_in_tmp, "card/closure")
        assert "from .card import closure_controller" in _init_text(app_in_tmp)


class TestStateChangeController:
    def test_pk_none_nested_resource(self, app_in_tmp):
        gen_controller(app_in_tmp, "card/closure")
        text = _closure_text(app_in_tmp)
        assert '@router.resource("cards/:card_id/closure", pk=None)' in text

    def test_class_mixes_in_concern(self, app_in_tmp):
        gen_controller(app_in_tmp, "card/closure")
        text = _closure_text(app_in_tmp)
        assert "class ClosureController(CardScoped, AppController):" in text

    def test_imports(self, app_in_tmp):
        gen_controller(app_in_tmp, "card/closure")
        text = _closure_text(app_in_tmp)
        assert "from ...router import router" in text
        assert "from ..app_controller import AppController" in text
        assert "from ..concerns.card_scoped import CardScoped" in text

    def test_create_and_delete_stubs(self, app_in_tmp):
        gen_controller(app_in_tmp, "card/closure")
        text = _closure_text(app_in_tmp)
        assert "def create(self):" in text
        assert "def delete(self):" in text
        assert "# TODO: apply the state change to self.card" in text
        assert "# TODO: undo the state change on self.card" in text
        assert 'self.response.redirect_to("Card.show", self.card, flash="...")' in text
        assert 'self.response.redirect_to("Card.show", self.card)' in text


class TestScopedConcern:
    def test_concern_class_and_callback(self, app_in_tmp):
        gen_controller(app_in_tmp, "card/closure")
        text = _concern_text(app_in_tmp)
        assert "class CardScoped(Concern):" in text
        assert 'before = {"do": "set_card"}' in text
        assert "def set_card(self):" in text
        assert "from ...models import Card" in text
        assert "self.card = Card.find(int(card_id))" in text

    def test_concern_not_clobbered_on_second_child(self, app_in_tmp):
        gen_controller(app_in_tmp, "card/closure")
        concern_path = _controllers(app_in_tmp) / "concerns" / "card_scoped.py"
        concern_path.write_text("# hand-edited\n")

        gen_controller(app_in_tmp, "card/not_now", only="create")

        assert concern_path.read_text() == "# hand-edited\n"


class TestActionFiltering:
    def test_only_create(self, app_in_tmp):
        gen_controller(app_in_tmp, "card/not_now", only="create")
        text = (_controllers(app_in_tmp) / "card" / "not_now_controller.py").read_text()
        assert "def create(self):" in text
        assert "def delete(self):" not in text

    def test_exclude_delete(self, app_in_tmp):
        gen_controller(app_in_tmp, "card/closure", exclude="delete")
        text = _closure_text(app_in_tmp)
        assert "def create(self):" in text
        assert "def delete(self):" not in text

    def test_excluding_all_leaves_pass_body(self, app_in_tmp):
        gen_controller(app_in_tmp, "card/closure", exclude="create,delete")
        text = _closure_text(app_in_tmp)
        assert "def create(self):" not in text
        assert "def delete(self):" not in text
        assert "    pass" in text


class TestMultiwordChild:
    def test_dasherized_path_and_pascal_class(self, app_in_tmp):
        gen_controller(app_in_tmp, "card/not_now")
        text = (_controllers(app_in_tmp) / "card" / "not_now_controller.py").read_text()
        assert '@router.resource("cards/:card_id/not-now", pk=None)' in text
        assert "class NotNowController(CardScoped, AppController):" in text


class TestPluralParent:
    def test_parent_is_pluralized(self, app_in_tmp):
        gen_controller(app_in_tmp, "company/closure")
        text = (_controllers(app_in_tmp) / "company" / "closure_controller.py").read_text()
        assert '@router.resource("companies/:company_id/closure", pk=None)' in text
        assert "from ..concerns.company_scoped import CompanyScoped" in text


class TestTestStub:
    def test_test_references_named_route(self, app_in_tmp):
        gen_controller(app_in_tmp, "card/closure")
        text = _test_text(app_in_tmp, "closure")
        assert "from myapp.main import app" in text
        assert "def test_closure_create(client):" in text
        assert "def test_closure_delete(client):" in text
        assert 'app.url_for("Closure.create", card_id=card.id)' in text


class TestForce:
    def test_skips_existing_controller_without_force(self, app_in_tmp):
        gen_controller(app_in_tmp, "card/closure")
        controller_path = _controllers(app_in_tmp) / "card" / "closure_controller.py"
        controller_path.write_text("# hand-edited\n")

        gen_controller(app_in_tmp, "card/closure")

        assert controller_path.read_text() == "# hand-edited\n"

    def test_force_overwrites_controller(self, app_in_tmp):
        gen_controller(app_in_tmp, "card/closure")
        controller_path = _controllers(app_in_tmp) / "card" / "closure_controller.py"
        controller_path.write_text("# hand-edited\n")

        gen_controller(app_in_tmp, "card/closure", force=True)

        assert "class ClosureController(CardScoped, AppController):" in controller_path.read_text()

    def test_init_import_added_only_once(self, app_in_tmp):
        gen_controller(app_in_tmp, "card/closure")
        gen_controller(app_in_tmp, "card/closure", force=True)
        assert _init_text(app_in_tmp).count("from .card import closure_controller") == 1


# --- A controller with form and views ---


ROUTE_RE = re.compile(r"""(?:url_for|redirect_to)\(\s*['"]([\w:]+)\.(\w+)['"]""")


def _read(app, *parts):
    return app.root_path.joinpath(*parts).read_text()


def _add_model(app, name_snake, name_pascal):
    init = app.root_path / "models" / "__init__.py"
    text = init.read_text() if init.exists() else ""
    init.write_text(f"{text}from .{name_snake} import {name_pascal}  # noqa\n")


def _linked_actions(app, name_snake, folder=""):
    """The actions that the generated controller and views link or redirect to."""
    texts = [_read(app, "controllers", folder, f"{name_snake}_controller.py")]
    views = app.root_path / "views" / folder / name_snake
    texts += [path.read_text() for path in views.glob("*.jx")]
    return {action for text in texts for _route, action in ROUTE_RE.findall(text)}


def _assert_valid_python(app, *parts):
    text = _read(app, *parts)
    compile(text, parts[-1], "exec")
    assert text.endswith("\n") and not text.endswith("\n\n")
    assert all(line == line.rstrip() for line in text.splitlines())


class TestWithModel:
    def test_uses_the_model(self, app_in_tmp):
        _add_model(app_in_tmp, "note", "Note")
        gen_controller(app_in_tmp, "Note", "title:str")

        controller = _read(app_in_tmp, "controllers", "note_controller.py")
        assert "from myapp.models import Note" in controller
        assert "self.notes = Note.select()" in controller
        assert "self.note = Note.find(int(note_id))" in controller
        assert "TODO" not in controller

        form = _read(app_in_tmp, "forms", "note.py")
        assert "from myapp.models import Note" in form
        assert "orm_cls = Note" in form
        assert "title = f.TextField()" in form

        assert "{#def notes #}" in _read(app_in_tmp, "views", "note", "index.jx")
        assert "{#def note #}" in _read(app_in_tmp, "views", "note", "show.jx")
        assert "{#def form, note #}" in _read(app_in_tmp, "views", "note", "edit.jx")
        _assert_valid_python(app_in_tmp, "controllers", "note_controller.py")
        _assert_valid_python(app_in_tmp, "forms", "note.py")

    def test_a_model_with_a_longer_name_is_not_the_model(self, app_in_tmp):
        _add_model(app_in_tmp, "notebook", "Notebook")
        gen_controller(app_in_tmp, "Note")
        assert "models" not in _read(app_in_tmp, "controllers", "note_controller.py")


class TestWithoutModel:
    """Regression: the generated code imported a model that didn't exist,
    and the app, with its `proper` command, could no longer start."""

    def test_does_not_import_a_model(self, app_in_tmp):
        gen_controller(app_in_tmp, "Note", "title:str")

        controller = _read(app_in_tmp, "controllers", "note_controller.py")
        assert "models" not in controller
        assert "proper.errors" not in controller
        assert "data = self.form.save()" in controller
        assert 'self.note_id = self.params.get("note_id", "")' in controller
        assert "self.form = NoteForm(self.params)" in controller

        form = _read(app_in_tmp, "forms", "note.py")
        assert "models" not in form
        assert "orm_cls" not in form
        assert "title = f.TextField()" in form
        _assert_valid_python(app_in_tmp, "controllers", "note_controller.py")
        _assert_valid_python(app_in_tmp, "forms", "note.py")

    def test_views_do_not_use_a_record(self, app_in_tmp):
        gen_controller(app_in_tmp, "Note", "title:str")

        assert "{#def" not in _read(app_in_tmp, "views", "note", "index.jx")
        show = _read(app_in_tmp, "views", "note", "show.jx")
        assert "{#def note_id #}" in show
        assert "url_for('Note.edit', note_id=note_id)" in show
        edit = _read(app_in_tmp, "views", "note", "edit.jx")
        assert "{#def form, note_id #}" in edit
        assert "url_for('Note.update', note_id=note_id)" in edit

    def test_without_attributes(self, app_in_tmp):
        gen_controller(app_in_tmp, "Note")

        form = _read(app_in_tmp, "forms", "note.py")
        assert form.endswith("class NoteForm(f.Form):\n    pass\n")
        _assert_valid_python(app_in_tmp, "controllers", "note_controller.py")
        _assert_valid_python(app_in_tmp, "forms", "note.py")

    def test_singular(self, app_in_tmp):
        gen_controller(app_in_tmp, "Setting", singular=True)

        controller = _read(app_in_tmp, "controllers", "setting_controller.py")
        assert "def set_setting" not in controller
        assert 'redirect_to("Setting.show", flash=' in controller
        assert "url_for('Setting.update')" in _read(app_in_tmp, "views", "setting", "edit.jx")
        assert "{#def form #}" in _read(app_in_tmp, "views", "setting", "edit.jx")
        _assert_valid_python(app_in_tmp, "controllers", "setting_controller.py")

    def test_only_index(self, app_in_tmp):
        gen_controller(app_in_tmp, "Report", only="index")

        controller = _read(app_in_tmp, "controllers", "report_controller.py")
        assert "forms" not in controller
        assert "before" not in controller
        assert "# Private" not in controller
        _assert_valid_python(app_in_tmp, "controllers", "report_controller.py")


class TestLinksToGeneratedActions:
    """Regression: the views and the redirects used routes of actions
    that were not generated, which fail with `RouteNotFound`."""

    @pytest.mark.parametrize("has_model", [True, False])
    @pytest.mark.parametrize("singular", [True, False])
    @pytest.mark.parametrize(
        "only",
        [
            "",
            "index",
            "index,show",
            "show",
            "new,create",
            "show,edit,update",
            "edit,update",
            "index,new,create,delete",
            "show,new,create,edit,update,delete",
            "create,update,delete",
        ],
    )
    def test_only_links_to_generated_actions(self, app_in_tmp, only, singular, has_model):
        if has_model:
            _add_model(app_in_tmp, "note", "Note")
        gen_controller(app_in_tmp, "Note", "title:str", only=only, singular=singular)

        generated = set(only.split(",")) if only else set(ACTIONS)
        if singular:
            generated.discard("index")
        assert _linked_actions(app_in_tmp, "note") <= generated
        _assert_valid_python(app_in_tmp, "controllers", "note_controller.py")

    def test_redirects_with_every_action(self, app_in_tmp):
        _add_model(app_in_tmp, "note", "Note")
        gen_controller(app_in_tmp, "Note")

        controller = _read(app_in_tmp, "controllers", "note_controller.py")
        assert 'redirect_to("Note.show", note, flash="Note was created")' in controller
        assert 'redirect_to("Note.show", note, flash="Note was updated")' in controller
        assert 'redirect_to("Note.index", flash="Note was deleted")' in controller

    def test_redirects_without_show(self, app_in_tmp):
        _add_model(app_in_tmp, "note", "Note")
        gen_controller(app_in_tmp, "Note", exclude="show")

        controller = _read(app_in_tmp, "controllers", "note_controller.py")
        assert 'redirect_to("Note.index", flash="Note was created")' in controller

    def test_redirects_without_index_or_show(self, app_in_tmp):
        _add_model(app_in_tmp, "note", "Note")
        gen_controller(app_in_tmp, "Note", only="new,create,delete")

        controller = _read(app_in_tmp, "controllers", "note_controller.py")
        assert 'redirect_to("/", flash="Note was created")' in controller
        assert 'redirect_to("/", flash="Note was deleted")' in controller

    def test_cancel_of_the_forms(self, app_in_tmp):
        _add_model(app_in_tmp, "note", "Note")
        gen_controller(app_in_tmp, "Note", exclude="index")

        assert "Cancel" not in _read(app_in_tmp, "views", "note", "new.jx")
        assert "url_for('Note.show', note) }}>Cancel" in _read(app_in_tmp, "views", "note", "edit.jx")


class TestNamespace:
    """Regression: the controller imported `admin_router` from `router.py`,
    but nothing defined it there."""

    ROUTER = '"""Routes"""\nfrom .main import app\n\n\nrouter = app.router\n'

    @pytest.fixture(autouse=True)
    def router_file(self, app_in_tmp):
        (app_in_tmp.root_path / "router.py").write_text(self.ROUTER)

    def test_adds_the_scoped_router(self, app_in_tmp):
        gen_controller(app_in_tmp, "Note", namespace="admin")

        assert _read(app_in_tmp, "router.py") == (
            self.ROUTER + '\nadmin_router = router.scope("admin")\n'
        )
        controller = _read(app_in_tmp, "controllers", "admin", "note_controller.py")
        assert "from myapp.router import admin_router" in controller
        assert '@admin_router.resource("notes")' in controller
        _assert_valid_python(app_in_tmp, "controllers", "admin", "note_controller.py")
        _assert_valid_python(app_in_tmp, "forms", "admin", "note.py")
        _assert_valid_python(app_in_tmp, "router.py")

    def test_adds_the_scoped_router_only_once(self, app_in_tmp):
        gen_controller(app_in_tmp, "Note", namespace="admin")
        gen_controller(app_in_tmp, "Tag", namespace="admin")
        gen_controller(app_in_tmp, "Note", namespace="admin", force=True)

        assert _read(app_in_tmp, "router.py").count("admin_router =") == 1
        init = _init_text(app_in_tmp)
        assert init.count("from .admin import note_controller") == 1
        assert init.count("from .admin import tag_controller") == 1

    def test_keeps_a_scoped_router_that_is_already_defined(self, app_in_tmp):
        text = self.ROUTER + '\nadmin_router = router.scope("backoffice")\n'
        (app_in_tmp.root_path / "router.py").write_text(text)

        gen_controller(app_in_tmp, "Note", namespace="admin")

        assert _read(app_in_tmp, "router.py") == text

    def test_each_namespace_has_its_router(self, app_in_tmp):
        gen_controller(app_in_tmp, "Note", namespace="admin")
        gen_controller(app_in_tmp, "Note", namespace="api")

        router = _read(app_in_tmp, "router.py")
        assert 'admin_router = router.scope("admin")' in router
        assert 'api_router = router.scope("api")' in router

    def test_creates_the_router_file_if_missing(self, app_in_tmp):
        (app_in_tmp.root_path / "router.py").unlink()
        gen_controller(app_in_tmp, "Note", namespace="admin")
        assert _read(app_in_tmp, "router.py") == 'admin_router = router.scope("admin")\n'

    def test_routes_have_the_prefix_of_the_namespace(self, app_in_tmp):
        _add_model(app_in_tmp, "note", "Note")
        gen_controller(app_in_tmp, "Note", namespace="admin")

        controller = _read(app_in_tmp, "controllers", "admin", "note_controller.py")
        assert 'redirect_to("Admin:Note.show", note' in controller
        assert "url_for('Admin:Note.new')" in _read(app_in_tmp, "views", "admin", "note", "index.jx")
        assert _linked_actions(app_in_tmp, "note", "admin") <= set(ACTIONS)

    def test_not_namespaced_does_not_touch_the_router(self, app_in_tmp):
        gen_controller(app_in_tmp, "Note")
        assert _read(app_in_tmp, "router.py") == self.ROUTER
