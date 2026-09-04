import sys

import pytest


@pytest.fixture()
def fast_switching():
    """Make the GIL hand off as often as it can, so thread interleavings
    that are otherwise vanishingly rare actually show up."""
    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    yield
    sys.setswitchinterval(previous)
