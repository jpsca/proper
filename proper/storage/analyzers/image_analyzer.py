from typing import TYPE_CHECKING

from .analyzer import Analyzer

if TYPE_CHECKING:
    from ..blob import Blob


class ImageAnalyzer(Analyzer):
    """This is an abstract base class for image analyzers,
    which extract width and height from an image blob.
    If the image contains EXIF data indicating its angle is 90 or 270 degrees,
    its width and height are swapped for convenience.
    """

    @classmethod
    def accepts(cls, blob: "Blob") -> bool:
        """Implement this method in a concrete subclass.
        Have it return True when given a blob from which the
        analyzer can extract metadata."""
        return blob.content_type.startswith("image/")

    def get_metadata(self) -> dict:
        image = self.read_image()
        if image.is_rotated:
            return {"width": image.height, "height": image.width}
        else:
            return {"width": image.width, "height": image.height}

    def read_image(self):
        raise NotImplementedError
