from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any
    from ..services import Service


class Analyzer:
    """This is an abstract base class for analyzers, which extract
    metadata from blobs. See image_analyzer_vips.py for an example
    of a concrete implementation.
    """

    # This will determine if blob analysis should be done in a task
    # or performed inline. By default, analysis is enqueued as a task.
    analyze_now = False

    @classmethod
    def accepts(cls, blob: "Any") -> bool:
        """Implement this method in a concrete subclass.
        Have it return True when given a blob from which the
        analyzer can extract metadata."""
        return False

    def __init__(self, service: "Service", blob: "Any") -> None:
        self.service = service
        self.blob = blob

    def get_metadata(self) -> dict:
        """Override this method in a concrete subclass. Have it return a dict
        with the metadata."""
        raise NotImplementedError
