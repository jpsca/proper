import pytest
from proper.router import delete, get, patch, post, put, resource


class Profile:
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


def test_singular_resource_with_callable():
    routes = resource("profile", to=Profile, singular=True)

    expected = [
        get("profile/new", to=Profile.new),
        post("profile/", to=Profile.create),
        get("profile", to=Profile.show),
        get("profile/edit", to=Profile.edit),
        patch("profile", to=Profile.update),
        put("profile", to=Profile.update),
        delete("profile", to=Profile.delete),
    ]

    print(routes)
    assert routes == expected


def test_singular_resource_only():
    routes = resource("profile", to=Profile, only=["show"], singular=True)

    expected = [
        get("profile", to=Profile.show),
    ]

    print(routes)
    assert routes == expected


def test_singular_resource_exclude():
    routes = resource(
        "profile", to=Profile, exclude=["new", "create", "delete"], singular=True
    )

    expected = [
        get("profile", to=Profile.show),
        get("profile/edit", to=Profile.edit),
        patch("profile", to=Profile.update),
        put("profile", to=Profile.update),
    ]

    print(routes)
    assert routes == expected


def test_some_invalid_actions():
    routes = resource(
        "profile", to=Profile, only=["index", "jump", "show", "fire"], singular=True
    )

    expected = [
        get("profile", to=Profile.show),
    ]

    print(routes)
    assert routes == expected


def test_only_invalid_actions():
    with pytest.raises(AssertionError):
        resource("profile", to=Profile, only=["ready", "set", "fire"], singular=True)

    with pytest.raises(AssertionError):
        resource("profile", to=Profile, only=[])


def test_only_and_exclude():
    routes = resource(
        "profile", to=Profile, only=["show", "update"], exclude=["show", "edit"], singular=True
    )

    expected = [
        patch("profile", to=Profile.update),
        put("profile", to=Profile.update),
    ]

    print(routes)
    assert routes == expected


def test_exclude_invalid():
    routes = resource(
        "profile", to=Profile, only=["show"], exclude=["patrice"], singular=True
    )

    expected = [
        get("profile", to=Profile.show),
    ]

    print(routes)
    assert routes == expected
