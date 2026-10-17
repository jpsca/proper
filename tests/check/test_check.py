import pytest

from proper.check import CHECKS, run_checks
from proper.cli.app_cli import get_check_cmd
from .conftest import FILES


def test_a_correct_app_has_no_problems(make_shop, capsys):
    app = make_shop()
    assert run_checks(app) == []
    capsys.readouterr()
    get_check_cmd(app)(None)
    assert capsys.readouterr().out == "No problems found.\n"


def test_the_command_lists_the_problems(make_shop, capsys):
    app = make_shop({
        "shop/main.py": FILES["shop/main.py"].replace(
            '"DEBUG": False,', '"DEBUG": False,\n        "MAX_FORM_FEILDS": 500,'
        ),
        "shop/views/post/show.jx": "<Card />\n",
    })
    capsys.readouterr()
    with pytest.raises(SystemExit) as exc:
        get_check_cmd(app)(None)
    assert exc.value.code == 1
    lines = capsys.readouterr().out.splitlines()
    assert lines == [
        "warning: unknown setting `MAX_FORM_FEILDS`: did you mean `MAX_FORM_FIELDS`?",
        lines[1],
        "1 error(s), 1 warning(s)",
    ]
    assert lines[1].startswith("shop/views/post/show.jx:1:1: error: ")


def test_warnings_alone_dont_fail(make_shop, capsys):
    app = make_shop({
        "shop/main.py": FILES["shop/main.py"].replace(
            '"DEBUG": False,', '"DEBUG": False,\n        "MAX_FORM_FEILDS": 500,'
        ),
    })
    get_check_cmd(app)(None)
    assert capsys.readouterr().out.splitlines()[-1] == "0 error(s), 1 warning(s)"


def test_the_command_is_registered(make_shop):
    app = make_shop()
    assert app.CLI.check.__doc__.startswith("Find the mistakes of the app")
    assert len(CHECKS) == 13
