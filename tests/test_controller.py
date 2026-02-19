"""
Tests for Controller functionality as documented in docs/controllers.md

This spec covers:
- Router resource decorator and CRUD action mapping
- ID parameter naming conventions
- Singular resources (pk=None)
- Custom pk argument
- Manual route decorators
- Controller params (query string, POST, and URL parameters)
- Controller callbacks (before/after)
- Callback options (only/exclude)
- Multiple callbacks and inheritance
- Controller concerns
"""
import pytest

from proper import Request, Response, status
from proper.concerns import Concern
from proper.constants import DELETE, GET, PATCH, POST, PUT
from proper.controller import Controller
from proper.errors import NotFound
from proper.router import Route


# =============================================================================
# Router Resource Decorator - CRUD Action Mapping
# =============================================================================


class CardController(Controller):
    """Full CRUD controller for testing resource routing."""

    def index(self):
        return "index"

    def new(self):
        return "new"

    def create(self):
        return "create"

    def show(self):
        return "show"

    def edit(self):
        return "edit"

    def update(self):
        return "update"

    def delete(self):
        return "delete"


def test_resource_maps_all_crud_actions(app):
    """router.resource maps index, new, create, show, edit, update, delete to URLs."""
    app.router.resource("cards")(CardController)

    expected = [
        Route(GET, "cards/", to=CardController.index),
        Route(GET, "cards/new", to=CardController.new),
        Route(POST, "cards/", to=CardController.create),
        Route(GET, "cards/:card_id", to=CardController.show),
        Route(GET, "cards/:card_id/edit", to=CardController.edit),
        Route(PATCH, "cards/:card_id", to=CardController.update),
        Route(PUT, "cards/:card_id", to=CardController.update),
        Route(DELETE, "cards/:card_id", to=CardController.delete),
    ]
    for i, route in enumerate(app.router.routes):
        expected[i].defaults = route.defaults
        assert route == expected[i]


class PartialCardController(Controller):
    """Controller with only some CRUD methods."""

    def index(self):
        return "index"

    def show(self):
        return "show"


def test_resource_only_maps_existing_methods(app):
    """router.resource only creates routes for methods that exist."""
    app.router.resource("cards")(PartialCardController)

    expected = [
        Route(GET, "cards/", to=PartialCardController.index),
        Route(GET, "cards/:partial_card_id", to=PartialCardController.show),
    ]
    for i, route in enumerate(app.router.routes):
        expected[i].defaults = route.defaults
        assert route == expected[i]


# =============================================================================
# ID Parameter Naming
# =============================================================================


class UserPhotoController(Controller):
    def show(self):
        return "show"


def test_id_param_derived_from_controller_name(app):
    """ID parameter is derived from snake-cased controller name."""
    # CardController -> card_id
    app.router.resource("cards")(CardController)

    routes_with_id = [r for r in app.router.routes if ":card_id" in r.path]
    assert len(routes_with_id) > 0


def test_id_param_for_compound_names(app):
    """Compound controller names produce compound ID params."""
    # UserPhotoController -> user_photo_id
    app.router.resource("photos")(UserPhotoController)

    routes_with_id = [r for r in app.router.routes if ":user_photo_id" in r.path]
    assert len(routes_with_id) == 1


# =============================================================================
# Custom pk Argument
# =============================================================================


def test_custom_pk_argument(app):
    """pk argument overrides the default ID parameter name."""
    app.router.resource("cards", pk="object")(CardController)

    routes_with_object_id = [r for r in app.router.routes if ":object_id" in r.path]
    routes_with_card_id = [r for r in app.router.routes if ":card_id" in r.path]

    assert len(routes_with_object_id) > 0
    assert len(routes_with_card_id) == 0


# =============================================================================
# Singular Resources (pk=None)
# =============================================================================


class ProfileController(Controller):
    """Singular resource - no ID needed."""

    def new(self):
        return "new"

    def create(self):
        return "create"

    def show(self):
        return "show"

    def edit(self):
        return "edit"

    def update(self):
        return "update"

    def delete(self):
        return "delete"


def test_singular_resource_no_id_in_urls(app):
    """pk=None creates routes without ID parameters."""
    app.router.resource("profile", pk=None)(ProfileController)

    expected = [
        Route(GET, "profile/new", to=ProfileController.new),
        Route(POST, "profile/", to=ProfileController.create),
        Route(GET, "profile", to=ProfileController.show),
        Route(GET, "profile/edit", to=ProfileController.edit),
        Route(PATCH, "profile", to=ProfileController.update),
        Route(PUT, "profile", to=ProfileController.update),
        Route(DELETE, "profile", to=ProfileController.delete),
    ]
    for i, route in enumerate(app.router.routes):
        expected[i].defaults = route.defaults
        assert route == expected[i]


class ProfileWithIndexController(Controller):
    """Singular resource that also has an index method."""

    def index(self):
        return "index"

    def show(self):
        return "show"


def test_singular_resource_ignores_index(app):
    """pk=None ignores the index method since it doesn't make sense."""
    app.router.resource("profile", pk=None)(ProfileWithIndexController)

    index_routes = [r for r in app.router.routes if r.to == ProfileWithIndexController.index]
    assert len(index_routes) == 0


# =============================================================================
# Manual Route Decorators
# =============================================================================


class PublicController(Controller):
    def index(self):
        return "home"

    def about(self):
        return "about"


def test_manual_get_route(app):
    """router.get creates a GET route for a method."""
    app.router.get("")(PublicController.index)

    route, params = app.router.match(GET, "/")
    assert route.to == PublicController.index


def test_manual_post_route(app):
    """router.post creates a POST route for a method."""
    app.router.post("submit")(PublicController.index)

    route, params = app.router.match(POST, "/submit")
    assert route.to == PublicController.index


def test_manual_patch_route(app):
    """router.patch creates a PATCH route for a method."""
    app.router.patch("update")(PublicController.index)

    route, params = app.router.match(PATCH, "/update")
    assert route.to == PublicController.index


def test_manual_delete_route(app):
    """router.delete creates a DELETE route for a method."""
    app.router.delete("remove")(PublicController.index)

    route, params = app.router.match(DELETE, "/remove")
    assert route.to == PublicController.index


# =============================================================================
# Controller Parameters
# =============================================================================


class ParamsController(Controller):
    def index(self):
        return f"status={self.params.get('status')}"

    def show(self):
        return f"card_id={self.params.get('card_id')}"

    def create(self):
        return f"name={self.params.get('name')}"


def test_query_string_params(app):
    """Query string parameters are available in self.params."""
    app.router.get("items")(ParamsController.index)

    resp = app.get("/items?status=activated")
    assert resp.body == "status=activated"


def test_url_params(app):
    """URL parameters (e.g., :card_id) are available in self.params."""
    app.router.get("cards/:card_id")(ParamsController.show)

    resp = app.get("/cards/42")
    assert resp.body == "card_id=42"


def test_form_params(app):
    """POST form parameters are available in self.params."""
    app.router.post("items")(ParamsController.create)

    resp = app.post("/items", data={"name": "Test Card"})
    assert resp.body == "name=Test Card"


# =============================================================================
# Controller Callbacks - Before
# =============================================================================


class BeforeCallbackController(Controller):
    before = {"do": "set_message"}

    def set_message(self):
        self.message = "before was called"

    def index(self):
        return self.message


def test_before_callback_runs_before_action(app):
    """Before callbacks run before the action."""
    app.router.get("items")(BeforeCallbackController.index)

    resp = app.get("/items")
    assert resp.body == "before was called"


class BeforeCallbackHaltController(Controller):
    before = {"do": "redirect_away"}

    def redirect_away(self):
        self.response.body = "redirected"

    def index(self):
        return "should not reach here"


def test_before_callback_can_halt_request(app):
    """Before callbacks can halt the request by setting a body or redirect."""
    app.router.get("items")(BeforeCallbackHaltController.index)

    resp = app.get("/items")
    assert resp.body == "redirected"


# =============================================================================
# Controller Callbacks - After
# =============================================================================


class AfterCallbackController(Controller):
    after = {"do": "add_header"}

    def add_header(self):
        self.response.headers.set("X-Custom", "after-called")

    def index(self):
        return "index"


def test_after_callback_runs_after_action(app):
    """After callbacks run after the action."""
    app.router.get("items")(AfterCallbackController.index)

    resp = app.get("/items")
    assert resp.headers.get("X-Custom") == "after-called"


# =============================================================================
# Callback Options - only/exclude
# =============================================================================


class OnlyCallbackController(Controller):
    before = {"do": "set_card", "only": ["show", "edit"]}

    def set_card(self):
        self.card = "loaded"

    def index(self):
        return f"card={getattr(self, 'card', 'not loaded')}"

    def show(self):
        return f"card={self.card}"


def test_callback_only_runs_for_specified_actions(app):
    """Callbacks with 'only' option only run for listed actions."""
    app.router.resource("cards")(OnlyCallbackController)

    # index is not in 'only', so set_card should not run
    resp = app.get("/cards")
    assert resp.body == "card=not loaded"

    # show is in 'only', so set_card should run
    resp = app.get("/cards/1")
    assert resp.body == "card=loaded"


class ExcludeCallbackController(Controller):
    before = {"do": "set_card", "exclude": ["index", "new"]}

    def set_card(self):
        self.card = "loaded"

    def index(self):
        return f"card={getattr(self, 'card', 'not loaded')}"

    def show(self):
        return f"card={self.card}"


def test_callback_exclude_skips_specified_actions(app):
    """Callbacks with 'exclude' option skip listed actions."""
    app.router.resource("cards")(ExcludeCallbackController)

    # index is excluded, so set_card should not run
    resp = app.get("/cards")
    assert resp.body == "card=not loaded"

    # show is not excluded, so set_card should run
    resp = app.get("/cards/1")
    assert resp.body == "card=loaded"


# =============================================================================
# Multiple Callbacks
# =============================================================================


class MultipleCallbacksController(Controller):
    before = [
        {"do": "first_callback"},
        {"do": "second_callback", "only": ["show"]},
    ]

    def first_callback(self):
        self.first = True

    def second_callback(self):
        self.second = True

    def index(self):
        first = getattr(self, "first", False)
        second = getattr(self, "second", False)
        return f"first={first},second={second}"

    def show(self):
        return f"first={self.first},second={self.second}"


def test_multiple_callbacks_execute_in_order(app):
    """Multiple callbacks execute in order with their own options."""
    app.router.resource("items")(MultipleCallbacksController)

    # index: first runs, second doesn't (only: show)
    resp = app.get("/items")
    assert resp.body == "first=True,second=False"

    # show: both run
    resp = app.get("/items/1")
    assert resp.body == "first=True,second=True"


# =============================================================================
# Callback Inheritance
# =============================================================================


class BaseController(Controller):
    before = {"do": "base_callback"}

    def base_callback(self):
        self.base = True


class ChildController(BaseController):
    before = {"do": "child_callback"}

    def child_callback(self):
        self.child = True

    def index(self):
        return f"base={self.base},child={self.child}"


def test_callbacks_inherited_from_parent(app):
    """Callbacks from parent classes are inherited and run first."""
    app.router.get("items")(ChildController.index)

    resp = app.get("/items")
    assert resp.body == "base=True,child=True"


# =============================================================================
# Controller Concerns
# =============================================================================


class SecurityHeaders(Concern):
    """A concern that adds security headers."""

    after = {"do": "set_security_headers"}

    def set_security_headers(self):
        self.response.headers.set("X-Security", "enabled")


class ConcernController(SecurityHeaders, Controller):
    def index(self):
        return "index"


def test_concern_adds_callbacks(app):
    """Concerns add their callbacks to the controller."""
    app.router.get("items")(ConcernController.index)

    resp = app.get("/items")
    assert resp.headers.get("X-Security") == "enabled"


class CardScoped(Concern):
    """Concern that loads a card from the card_id param."""

    before = {"do": "set_card"}

    def set_card(self):
        card_id = self.params.get("card_id")
        if card_id:
            # Simulate loading a card
            self.card = {"id": card_id, "title": "Test Card"}


class CardClosureController(CardScoped, Controller):
    """Controller that uses the CardScoped concern."""

    def create(self):
        return f"closing card {self.card['id']}"

    def delete(self):
        return f"reopening card {self.card['id']}"


def test_concern_with_before_callback(app):
    """Concerns can define before callbacks that load data."""
    app.router.resource("cards/:card_id/closure", pk=None)(CardClosureController)

    resp = app.post("/cards/42/closure")
    assert resp.body == "closing card 42"

    resp = app.delete("/cards/42/closure")
    assert resp.body == "reopening card 42"


# =============================================================================
# Nested Resources (Everything is CRUD)
# =============================================================================


def test_nested_resource_routing(app):
    """Nested resources use parent ID in the URL path."""

    class CommentController(Controller):
        def index(self):
            return f"comments for card {self.params.get('card_id')}"

        def create(self):
            return f"create comment on card {self.params.get('card_id')}"

    app.router.resource("cards/:card_id/comments")(CommentController)

    resp = app.get("/cards/42/comments")
    assert resp.body == "comments for card 42"

    resp = app.post("/cards/42/comments")
    assert resp.body == "create comment on card 42"
