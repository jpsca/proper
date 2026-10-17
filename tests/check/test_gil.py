import pytest

from proper.check import ERROR, WARNING, Problem, gil
from proper.check.gil import check_gil, modules_that_enable_the_gil


WARNS = """
    import warnings

    for _ in range(2):
        warnings.warn(
            "The global interpreter lock (GIL) has been enabled to load module "
            "'shop._speedups', which has not declared that it can run safely "
            "without the GIL.",
            RuntimeWarning,
        )
"""


def test_without_the_gil(make_shop):
    app = make_shop()
    assert gil.free_threaded()
    assert not gil.gil_enabled()
    assert check_gil(app) == []


def test_allowed_gil(make_shop, monkeypatch):
    app = make_shop()
    monkeypatch.setattr(gil, "gil_enabled", lambda: True)
    app.config.ALLOW_GIL = True
    [problem] = check_gil(app)
    assert problem.level == WARNING


def test_a_python_with_the_gil(make_shop, monkeypatch):
    app = make_shop()
    monkeypatch.setattr(gil, "gil_enabled", lambda: True)
    monkeypatch.setattr(gil, "free_threaded", lambda: False)
    [problem] = check_gil(app)
    assert problem.level == ERROR
    assert "this Python has the GIL" in problem.message


@pytest.mark.filterwarnings("ignore:The global interpreter lock:RuntimeWarning")
def test_a_module_that_turns_the_gil_on(make_shop, monkeypatch):
    """The app is imported again in a new process, where Python warns."""
    app = make_shop({
        "shop/__init__.py": "from . import main, router, controllers, models, forms, emails  # noqa\n",
        "shop/main.py": "from . import speedups  # noqa\n" + open_main(),
        "shop/speedups.py": WARNS,
    })
    monkeypatch.setattr(gil, "gil_enabled", lambda: True)
    assert modules_that_enable_the_gil("shop") == ["shop._speedups"]
    assert check_gil(app) == [Problem(
        ERROR,
        "importing the app turns the GIL back on, so `proper run` refuses to start: "
        "`shop._speedups` not declared safe without it. Upgrade or replace it "
        "(or set ALLOW_GIL = True)",
    )]


def test_the_gil_on_without_a_module(make_shop, monkeypatch):
    app = make_shop()
    monkeypatch.setattr(gil, "gil_enabled", lambda: True)
    [problem] = check_gil(app)
    assert problem.message == "the GIL is on (is PYTHON_GIL=1 set?), so `proper run` refuses to start"


def open_main():
    import textwrap

    from .conftest import FILES

    return textwrap.dedent(FILES["shop/main.py"]).lstrip()
