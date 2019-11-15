import pytest

from proper.support import cached_property


class Class(object):
    @cached_property
    def value(self):
        """A docstring"""
        return "abc", object()

    @cached_property
    def __foo__(self):
        """A docstring"""
        return "abc", object()

    def other_value(self):
        """A docstring"""
        return "abc", object()

    other = cached_property(other_value, name="other")


class SubClass(Class):
    pass


@pytest.mark.parametrize("attr", ["value", "__foo__", "other"])
def test_persist_dosctring(attr):
    assert getattr(Class, attr).__doc__ == "A docstring"
    assert getattr(SubClass, attr).__doc__ == "A docstring"


@pytest.mark.parametrize("attr", ["value", "__foo__", "other"])
def test_cached(attr):
    obj = Class()
    subobj = SubClass()

    assert getattr(obj, attr) == getattr(obj, attr)
    assert getattr(subobj, attr) == getattr(subobj, attr)

    assert getattr(obj, attr)[0] == "abc"
    assert getattr(subobj, attr)[0] == "abc"


@pytest.mark.parametrize("attr", ["value", "__foo__", "other"])
def test_not_shared(attr):
    obj = Class()
    obj2 = Class()
    subobj = SubClass()
    subobj2 = SubClass()

    assert getattr(obj, attr) != getattr(obj2, attr)
    assert getattr(subobj, attr) != getattr(subobj2, attr)


@pytest.mark.parametrize("attr", ["value", "__foo__", "other"])
def test_like_property(attr):
    assert isinstance(getattr(Class, attr), cached_property)
    assert isinstance(getattr(SubClass, attr), cached_property)


def test_custom_doc():
    obj = Class()
    obj.custom = cached_property(obj.other_value, doc="Hello")

    assert obj.custom.__doc__ == "Hello"


def test_custom_name():
    obj = Class()
    obj.custom = cached_property(obj.other_value, name="yeah")

    assert obj.custom.__name__ == "yeah"
