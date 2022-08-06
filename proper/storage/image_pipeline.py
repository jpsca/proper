from typing import TYPE_CHECKING

from image_processing import ImageProcessing

if TYPE_CHECKING:
    from .file_data import FileData
    from .storage import Storage


class ImagePipeline(ImageProcessing):
    def __init__(self, storage: "Storage", fdata: "FileData"):
        self.fdata = fdata
        self.storage = storage
        super().__init__()

    def get_url(self) -> str:
        pass

    def _get_uid(self):
        """Returns an unique identifier for the preview based on the
        hash of the original file and the options of the image
        processing pipeline.
        """
        pass

