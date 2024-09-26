import typing as t


if t.TYPE_CHECKING:
    from proper.controller import Controller


class Concern:
    def before(self, co: "Controller") -> t.Any:
        pass

    def after(self, co: "Controller") -> t.Any:
        pass

