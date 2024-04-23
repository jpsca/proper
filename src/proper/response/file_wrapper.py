import typing as t

from proper.types import TReadable


class FileWrapper:
    """This class can be used to convert a file-like object into
    an iterable. It yields `block_size` blocks until the file is fully read.
    You should not use this class directly but rather use the
    `Request.wrap_file` method that uses the WSGI server's file wrapper
    support if it's available.

    More information about file wrappers is available in
    [PEP 3333](https://peps.python.org/pep-3333/#optional-platform-specific-file-handling).


    Arguments:

        file:
            a `file`-like object with a `read` method.

        block_size:
            number of bytes for one iteration.

    """

    def __init__(self, filelike: TReadable, block_size: int = 8192) -> None:
        self.filelike = filelike
        self.block_size = block_size

    def close(self) -> None:
        if hasattr(self.filelike, "close"):
            self.filelike.close()

    def seekable(self) -> bool:
        if hasattr(self.filelike, "seekable"):
            return self.filelike.seekable()
        if hasattr(self.filelike, "seek"):
            return True
        return False

    def seek(self, *args: t.Any) -> None:
        if hasattr(self.filelike, "seek"):
            self.filelike.seek(*args)

    def tell(self) -> int | None:
        if hasattr(self.filelike, "tell"):
            return self.filelike.tell()
        return None

    def __iter__(self) -> "FileWrapper":
        return self

    def __next__(self) -> bytes:
        data = self.filelike.read(self.block_size)
        if data:
            return data
        raise StopIteration()
