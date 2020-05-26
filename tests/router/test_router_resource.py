import pytest

from proper.router import delete, get, patch, post, put, resources, scope


def test_basic_resources():
    routes = resources("posts", to="Posts")

    expected = [
        get("posts", to="Posts.index"),
        get("posts/:uid", to="Posts.show"),
        get("posts/new", to="Posts.new"),
        post("posts", to="Posts.create"),
        get("posts/:uid/edit", to="Posts.edit"),
        patch("posts/:uid", to="Posts.update"),
        put("posts/:uid", to="Posts.update"),
        delete("posts/:uid", to="Posts.delete"),
    ]

    assert routes == expected


def test_basic_resources_mounted():
    routes = scope("/mount/")(resources("posts", to="Posts"))

    expected = scope("/mount/")(
        get("posts/", to="Posts.index"),
        get("posts/:uid", to="Posts.show"),
        get("posts/new", to="Posts.new"),
        post("posts/", to="Posts.create"),
        get("posts/:uid/edit", to="Posts.edit"),
        patch("posts/:uid", to="Posts.update"),
        put("posts/:uid", to="Posts.update"),
        delete("posts/:uid", to="Posts.delete"),
    )

    assert routes == expected


class MyController(object):
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


def test_resources_with_callable():
    routes = resources("posts", to=MyController)

    expected = [
        get("posts/", to=MyController.index),
        get("posts/:uid", to=MyController.show),
        get("posts/new", to=MyController.new),
        post("posts/", to=MyController.create),
        get("posts/:uid/edit", to=MyController.edit),
        patch("posts/:uid", to=MyController.update),
        put("posts/:uid", to=MyController.update),
        delete("posts/:uid", to=MyController.delete),
    ]

    assert routes == expected


def test_resources_only():
    routes = resources("posts", to="Posts", only=["index", "show"])

    expected = [get("posts/", to="Posts.index"), get("posts/:uid", to="Posts.show")]

    assert routes == expected


def test_resources_ignore():
    routes = resources("posts", to="Posts", ignore=["new", "create", "delete"])

    expected = [
        get("posts/", to="Posts.index"),
        get("posts/:uid", to="Posts.show"),
        get("posts/:uid/edit", to="Posts.edit"),
        patch("posts/:uid", to="Posts.update"),
        put("posts/:uid", to="Posts.update"),
    ]

    assert routes == expected


def test_some_invalid_actions():
    routes = resources("posts", to="Posts", only=["index", "jump", "show", "fire"])

    expected = [get("posts/", to="Posts.index"), get("posts/:uid", to="Posts.show")]

    assert routes == expected


def test_only_invalid_actions():
    with pytest.raises(AssertionError):
        resources("posts", to="Posts", only=["ready", "set", "fire"])

    with pytest.raises(AssertionError):
        resources("posts", to="Posts", only=[])


def test_only_and_ignore():
    routes = resources(
        "posts", to="Posts", only=["index", "show"], ignore=["show", "edit"]
    )

    expected = [get("posts/", to="Posts.index")]

    assert routes == expected


def test_ignore_invalid():
    routes = resources("posts", to="Posts", only=["index", "show"], ignore=["patrice"])

    expected = [get("posts/", to="Posts.index"), get("posts/:uid", to="Posts.show")]

    assert routes == expected
