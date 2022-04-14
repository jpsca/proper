from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from ..blob import Blob

if TYPE_CHECKING:
    from typing import IO
    from proper import App


class BaseService(ABC):
    def __init__(self, app: "App", **kwargs) -> None:
        self.app = app
        self.config = kwargs

    @abstractmethod
    def save(self, filesto: "IO", blob: "Blob") -> "Blob":
        return blob
