import typing as t

if t.TYPE_CHECKING:
    from proper import App


def install(app: "App") -> None:
    """Install storage support.
    """
