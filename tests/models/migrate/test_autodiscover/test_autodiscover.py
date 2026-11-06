import pytest

from proper.models.migrate.router import load_models


@pytest.mark.parametrize(
    ("path", "expected_count"),
    [
        (f"{__package__}.models1", 3),
        (f"{__package__}.models2", 4),
        (f"{__package__}.models3", 3),
    ],
)
def test_load_models(path, expected_count):
    result = load_models(path)
    assert len(result) == expected_count


def test_load_models_parent():
    result = load_models(__package__)
    assert len(result) == 10
