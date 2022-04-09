from abc import ABC, abstractmethod
from typing import IO

from ..blob import Blob


class BaseService(ABC):
    def __init__(self, app, **kwargs):
        self.app = app
        self.config = kwargs

    @abstractmethod
    def save(self, filesto: IO, blob: Blob) -> None:
        return blob
