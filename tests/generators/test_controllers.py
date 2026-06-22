import pytest

from proper.generators.controller import gen_controller


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
        assert "self.card = Card.get_or_none(id=int(card_id))" in text

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
