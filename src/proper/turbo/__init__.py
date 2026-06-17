import mimetypes

from ..constants import TURBO_STREAM_MIME
from .frame import turbo_frame_tag
from .stream import turbo_stream


# Registering the MIME lets the template resolver route a Turbo request to a
# `{action}.turbo_stream.jx` view automatically, the same way it already routes
# `.html`/`.json` by the `Accept` header.
mimetypes.add_type(TURBO_STREAM_MIME, ".turbo_stream")


__all__ = (
    "TURBO_STREAM_MIME",
    "turbo_frame_tag",
    "turbo_stream",
)
