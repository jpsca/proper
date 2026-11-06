import pytest


@pytest.mark.parametrize("dburl", ["postgres://localhost:5432/test"])
def test_base(migrator, database):
    migrator()
    queries = database.cursor().queries
    assert queries
