import pytest

from .helpers import Expected, Project


# The tests compile the .jx files of the fixtures to modules next to them
collect_ignore_glob = ["fixtures/*"]


@pytest.fixture
def expected(request):
    """What Jx rendered in this test, in order; all of it must be used."""
    recorded = Expected(f"{request.node.path.name}::{request.node.name}")
    yield recorded
    recorded.check_all_used()


@pytest.fixture(params=[False, True], ids=["plain", "autoescape"])
def project(tmp_path, request, expected) -> Project:
    """Every golden test runs twice: without autoescape and with it."""
    return Project(tmp_path, expected, autoescape=request.param)
