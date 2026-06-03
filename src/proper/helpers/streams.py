import typing as t


def copy_file(
    stream: t.IO[bytes],
    target: t.IO[bytes],
    maxread: int = -1,
    buffer_size: int = 2 ** 16,
) -> int:
    """Read from *stream* and write to *target* until *maxread* or EOF."""
    size, read = 0, stream.read

    while True:
        to_read = buffer_size if maxread < 0 else min(buffer_size, maxread - size)
        part = read(to_read)

        if not part:
            return size

        target.write(part)
        size += len(part)
