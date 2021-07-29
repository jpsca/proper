import pytest

from proper.router import delete, get, patch, post, put, resource


class Posts:
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


def test_resource():
    routes = resource("posts", to=Posts)

    expected = [
        get("posts/", to=Posts.index),
        get("posts/new", to=Posts.new),
        post("posts/", to=Posts.create),
        get("posts/:uid", to=Posts.show),
        get("posts/:uid/edit", to=Posts.edit),
        patch("posts/:uid", to=Posts.update),
        put("posts/:uid", to=Posts.update),
        delete("posts/:uid", to=Posts.delete),
    ]

    print(routes)
    assert routes == expected


def test_resource_only():
    routes = resource("posts", to=Posts, only=["index", "show"])

    expected = [
        get("posts/", to=Posts.index),
        get("posts/:uid", to=Posts.show),
    ]

    print(routes)
    assert routes == expected


def test_resource_ignore():
    routes = resource("posts", to=Posts, ignore=["new", "create", "delete"])

    expected = [
        get("posts/", to=Posts.index),
        get("posts/:uid", to=Posts.show),
        get("posts/:uid/edit", to=Posts.edit),
        patch("posts/:uid", to=Posts.update),
        put("posts/:uid", to=Posts.update),
    ]

    print(routes)
    assert routes == expected


def test_some_invalid_actions():
    routes = resource("posts", to=Posts, only=["index", "jump", "show", "fire"])

    expected = [
        get("posts/", to=Posts.index),
        get("posts/:uid", to=Posts.show),
    ]

    print(routes)
    assert routes == expected


def test_only_invalid_actions():
    with pytest.raises(AssertionError):
        resource("posts", to=Posts, only=["ready", "set", "fire"])

    with pytest.raises(AssertionError):
        resource("posts", to=Posts, only=[])


def test_only_and_ignore():
    routes = resource(
        "posts", to=Posts, only=["index", "show"], ignore=["show", "edit"]
    )

    expected = [
        get("posts/", to=Posts.index),
    ]

    print(routes)
    assert routes == expected


def test_ignore_invalid():
    routes = resource("posts", to=Posts, only=["index", "show"], ignore=["patrice"])

    expected = [
        get("posts/", to=Posts.index),
        get("posts/:uid", to=Posts.show),
    ]

    print(routes)
    assert routes == expected
