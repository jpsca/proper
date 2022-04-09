from typing import IO

from ..blob import Blob
from .base import BaseService


class S3Service(BaseService):
    def save(self, filesto: IO, blob: Blob) -> None:
        return blob
