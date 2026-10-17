from proper.check import ERROR, WARNING
from proper.check.actions import check_action_names
from .conftest import extend


CONTROLLERS = """

    class Base(Controller):
        before = [{"do": "load", "exclude": ["index", "neww"]}, "load"]

        def load(self):
            pass


    class ItemController(Base):
        skip_authentication = ["index", "shw"]
        rate_limit = [
            {"to": 5, "within": "window", "only": "creat", "by": lambda self: 1},
            {"to": "limit", "within": 60},
            "not a limit",
        ]
        after = {"do": "log", "only": ["index"]}

        @router.get("items")
        def index(self):
            pass

        def log(self):
            pass

        def limit(self):
            return 5


    class OtherController(Base):
        skip_authentication = True

        @router.get("others")
        def index(self):
            pass


    def make():
        class HiddenController(Controller):
            @router.get("hidden")
            def index(self):
                pass

            @router.error(KeyError)
            def oops(self):
                pass

    make()
    router.get("old-items", redirect="/items")
"""


def test_action_names(make_shop):
    app = make_shop(extend("shop/controllers.py", CONTROLLERS))
    problems = sorted(check_action_names(app), key=lambda p: p.line)
    assert [(p.level, p.message, p.line) for p in problems] == [
        (
            WARNING,
            "`exclude` of the `before` callback `load` names `neww`, which is not "
            "an action of any controller based on Base",
            21,
        ),
        (WARNING, "`skip_authentication` names `shw`, which is not an action of ItemController", 28),
        (WARNING, "`only` of `rate_limit` names `creat`, which is not an action of ItemController", 29),
        (ERROR, "`within` of `rate_limit` names `window`, which is not a method of ItemController", 29),
    ]
    assert {p.path for p in problems} == {"shop/controllers.py"}


def test_right_action_names(make_shop):
    app = make_shop()
    assert check_action_names(app) == []
