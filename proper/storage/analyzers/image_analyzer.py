import logging
from typing import TYPE_CHECKING

try:
    import pyvips
except (ImportError, OSError):
    pyvips = None

from .analyzer import Analyzer

if TYPE_CHECKING:
    from ..file_data import Blob


logger = logging.getLogger("proper")

IMPORT_ERROR = """Missing `libvips` library
To analyze an image you need `libvips` installed
Please visit https://www.libvips.org/install.html
for instructions on how to do it in your system."""
ROTATIONS = ("Right-top", "Left-bottom", "Top-right", "Bottom-left")


class ImageAnalyzer(Analyzer):
    """If the image contains EXIF data indicating its angle is
    90 or 270 degrees, its width and height are swapped for convenience.
    """

    @classmethod
    def accepts(cls, blob: "Blob") -> bool:
        if not blob.content_type.startswith("image/"):
            return False

        if pyvips is None:
            raise ImportError(IMPORT_ERROR)
        return True

    def read_image(self) -> "pyvips.Image":
        path = self.service.download_blob_to_tempfile(self.blob)
        try:
            image = pyvips.Image.new_from_file(path, access="sequential")
        except pyvips.Error as error:
            logger.error("Skipping image analysis due to an Vips error: %s", error.message)
            return
        if not self.is_valid_image(image):
            logger.info("Skipping image analysis because Vips doesn't support the file")
            return
        return image

    def is_valid_image(self, image: "pyvips.Image") -> bool:
        try:
            image.avg
            return True
        except pyvips.Error:
            return False

    def is_rotated(self, image: "pyvips.Image") -> bool:
        try:
            return image.get("exif-ifd0-Orientation") in ROTATIONS
        except pyvips.Error:
            return False

    def get_metadata(self) -> dict:
        image = self.read_image()
        if self.is_rotated(image):
            return {"width": image.height, "height": image.width}
        else:
            return {"width": image.width, "height": image.height}

