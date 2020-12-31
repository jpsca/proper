from proper import BaseController


class MyTestController(BaseController):

    foo = "bar"
    _lorem = "ipsum"

    @property
    def lorem(self):
        return self._lorem

    def hello(self):
        pass

    def _render(self, *args, **kwargs):
        pass


def test_as_dict():
    data = MyTestController(None)._as_dict()

    assert "foo" in data
    assert "hello" in data
    assert "lorem" in data

    assert "_lorem" not in data
    assert "_render" not in data

    assert data["foo"] == "bar"
    assert data["lorem"] == "ipsum"
    assert callable(data["hello"])
