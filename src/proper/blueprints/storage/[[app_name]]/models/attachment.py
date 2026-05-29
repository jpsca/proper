from ..main import app
from .base import BaseModel


class Attachment(app.attachment_for(BaseModel)):
    # You can add any extra fields here, like:
    # user = pw.ForeignKeyField(User, null=True)
    # etc.

    # All of these previewers are included but each of them require extra
    # python packages and/or *system* libraries.
    #
    # Uncomment the ones you want to use and make sure to install the
    # required dependencies. Note that you can also add your own custom previewers.
    #
    # Read the storage docs for details https://properproject.org/docs/storage/.
    VARIANTS_ENABLED_FOR = {
        # Requires the `pyvips` python library and the
        # [libvips](https://www.libvips.org/install.html) system library.
        "image/*": "preview_image",

        # Requires [poppler](https://poppler.freedesktop.org/).
        # "application/pdf": "preview_pdf",

        # Requires [ffmpeg v3.4+](https://ffmpeg.org/)
        # "video/*": "preview_video",
    }
    ...
