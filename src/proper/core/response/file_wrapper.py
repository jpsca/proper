import typing as t

from ...types import TReadable


__all__ = ("FileWrapper",)


class FileWrapper:
    """Converts a file-like object into an iterable of chunks.

    Yields `block_size` blocks until the file is fully read.
    Used by `Response.send_file` to stream file responses without
    buffering the entire file in memory.

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
