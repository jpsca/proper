import typing as t


if t.TYPE_CHECKING:
    from proper.view import View


class Concern:
    def before(self, view: "View") -> t.Any:
        pass

    def after(self, view: "View") -> t.Any:
        pass

