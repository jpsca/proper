from proper.base_controller import BaseController


class MyTestController(BaseController):

    foo = "bar"
    _lorem = "ipsum"

    @property
    def lorem(self):
        return self._lorem

    def hello():
        pass

    def _render(*args, **kwargs):
        pass


def test_as_dict():
    data = MyTestController()._as_dict()

    assert "foo" in data
    assert "hello" in data
    assert "lorem" in data

    assert "_lorem" not in data
    assert "_render" not in data

    assert data["foo"] == "bar"
    assert data["lorem"] == "ipsum"
    assert callable(data["hello"])
