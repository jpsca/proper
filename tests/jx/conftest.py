"""
Jx | Copyright (c) Juan-Pablo Scaletti
"""

import pytest


@pytest.fixture()
def folder(tmp_path):
    d = tmp_path / "views"
    d.mkdir()
    return d
