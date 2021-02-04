import pytest

from proper.router import delete, get, patch, post, put, resource


def test_singular_resource():
    routes = resource("profile", to="Profile", singular=True)

    expected = [
        get("profile/new", to="Profile.new"),
        post("profile", to="Profile.create"),
        get("profile", to="Profile.show"),
        get("profile/edit", to="Profile.edit"),
        patch("profile", to="Profile.update"),
        put("profile", to="Profile.update"),
        delete("profile", to="Profile.delete"),
    ]

    print(routes)
    assert routes == expected


class MyController:
    def index(self, req, resp):
        pass

    def show(self, req, resp):
        pass

    def new(self, req, resp):
        pass

    def create(self, req, resp):
        pass

    def edit(self, req, resp):
        pass

    def update(self, req, resp):
        pass

    def delete(self, req, resp):
        pass


def test_singular_resource_with_callable():
    routes = resource("profile", to=MyController, singular=True)

    expected = [
        get("profile/new", to=MyController.new),
        post("profile/", to=MyController.create),
        get("profile", to=MyController.show),
        get("profile/edit", to=MyController.edit),
        patch("profile", to=MyController.update),
        put("profile", to=MyController.update),
        delete("profile", to=MyController.delete),
    ]

    print(routes)
    assert routes == expected


def test_singular_resource_only():
    routes = resource("profile", to="Profile", only=["show"], singular=True)

    expected = [
        get("profile", to="Profile.show"),
    ]

    print(routes)
    assert routes == expected


def test_singular_resource_ignore():
    routes = resource(
        "profile", to="Profile", ignore=["new", "create", "delete"], singular=True
    )

    expected = [
        get("profile", to="Profile.show"),
        get("profile/edit", to="Profile.edit"),
        patch("profile", to="Profile.update"),
        put("profile", to="Profile.update"),
    ]

    print(routes)
    assert routes == expected


def test_some_invalid_actions():
    routes = resource(
        "profile", to="Profile", only=["index", "jump", "show", "fire"], singular=True
    )

    expected = [
        get("profile", to="Profile.show"),
    ]

    print(routes)
    assert routes == expected


def test_only_invalid_actions():
    with pytest.raises(AssertionError):
        resource("profile", to="Profile", only=["ready", "set", "fire"], singular=True)

    with pytest.raises(AssertionError):
        resource("profile", to="Profile", only=[])


def test_only_and_ignore():
    routes = resource(
        "profile", to="Profile", only=["show", "update"], ignore=["show", "edit"], singular=True
    )

    expected = [
        patch("profile", to="Profile.update"),
        put("profile", to="Profile.update"),
    ]

    print(routes)
    assert routes == expected


def test_ignore_invalid():
    routes = resource(
        "profile", to="Profile", only=["show"], ignore=["patrice"], singular=True
    )

    expected = [
        get("profile", to="Profile.show"),
    ]

    print(routes)
    assert routes == expected
