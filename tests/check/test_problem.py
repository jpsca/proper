from proper.check import ERROR, WARNING, Problem
from proper.check.problem import relpath, subclasses, where, where_attr


def test_how_a_problem_prints():
    assert str(Problem(ERROR, "bad")) == "error: bad"
    assert str(Problem(WARNING, "odd", path="a.py")) == "a.py: warning: odd"
    assert str(Problem(ERROR, "bad", path="a.py", line=3)) == "a.py:3: error: bad"
    assert str(Problem(ERROR, "bad", path="a.jx", line=3, col=9)) == "a.jx:3:9: error: bad"


def test_relpath(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert relpath(tmp_path / "db" / "main") == "db/main"
    assert relpath("/somewhere/else.py") == "/somewhere/else.py"


class Tag:
    name = "tag"

    def label(self):
        return self.name


def test_where():
    assert where(Tag)["path"].endswith("tests/check/test_problem.py")
    assert where(Tag)["line"] == 18
    assert where_attr(Tag, "name")["line"] == 19
    assert where_attr(Tag, "missing")["line"] == 18


def test_where_without_source():
    assert where(len) == {}
    assert where_attr(int, "real") == {}


def test_subclasses_once():
    class A: ...
    class B(A): ...
    class C(A): ...
    class D(B, C): ...

    assert subclasses(A) == [B, C, D]
