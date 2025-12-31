from proper.constants import DELETE, GET, PATCH, POST, PUT
from proper.controller import Controller
from proper.router import Route


class PartialController(Controller):
    def index(self):
        pass

    def show(self):
        pass


class FullController(Controller):
    def index(self):
        pass

    def show(self):
        pass

    def new(self):
        pass

    def create(self):
        pass

    def edit(self):
        pass

    def update(self):
        pass

    def delete(self):
        pass


def test_resource(app):
    app.router.resource("posts")(FullController)

    expected = [
        Route(GET, "posts/", to=FullController.index),
        Route(GET, "posts/new", to=FullController.new),
        Route(POST, "posts/", to=FullController.create),
        Route(GET, "posts/:full_id", to=FullController.show),
        Route(GET, "posts/:full_id/edit", to=FullController.edit),
        Route(PATCH, "posts/:full_id", to=FullController.update),
        Route(PUT, "posts/:full_id", to=FullController.update),
        Route(DELETE, "posts/:full_id", to=FullController.delete),
    ]
    for route in app.router.routes:
        print(route)
    for i, route in enumerate(app.router.routes):
        expected[i].defaults = route.defaults
        assert route == expected[i]


def test_partial_resource(app):
    app.router.resource("posts")(PartialController)

    expected = [
        Route(GET, "posts/", to=PartialController.index),
        Route(GET, "posts/:partial_id", to=PartialController.show),
    ]
    for route in app.router.routes:
        print(route)
    for i, route in enumerate(app.router.routes):
        expected[i].defaults = route.defaults
        assert route == expected[i]


def test_resource_singular(app):
    app.router.resource("profile", pk=None)(FullController)

    expected = [
        Route(GET, "profile/new", to=FullController.new),
        Route(POST, "profile/", to=FullController.create),
        Route(GET, "profile", to=FullController.show),
        Route(GET, "profile/edit", to=FullController.edit),
        Route(PATCH, "profile", to=FullController.update),
        Route(PUT, "profile", to=FullController.update),
        Route(DELETE, "profile", to=FullController.delete),
    ]
    for route in app.router.routes:
        print(route)
    for i, route in enumerate(app.router.routes):
        expected[i].defaults = route.defaults
        assert route == expected[i]
