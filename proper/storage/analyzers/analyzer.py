from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..blob import Blob


class Analyzer:
    """This is an abstract base class for analyzers, which extract
    metadata from blobs. See image_analyzer_vips.py for an example
    of a concrete implementation.
    """

    @classmethod
    def accepts(cls, blob: "Blob") -> bool:
        """Implement this method in a concrete subclass.
        Have it return True when given a blob from which the
        analyzer can extract metadata."""
        return False

    def __init__(self, blob: "Blob") -> None:
        self.blob = blob

    def get_metadata(self) -> dict:
        """Override this method in a concrete subclass. Have it return a dict
        with the metadata."""
        raise NotImplementedError
