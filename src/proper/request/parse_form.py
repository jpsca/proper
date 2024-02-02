import json
import typing as t
from urllib.parse import parse_qs

from proper.errors import (
    BadRequest,
    MultipartError,
    RequestEntityTooLarge,
    UnsupportedMediaType,
    UriTooLong,
)
from proper.helpers import MultiDict

from .multipart import (
    MultipartParser,
    parse_options_header,
)


def parse_form(
    stream: t.IO[bytes],
    content_type: str,
    content_length: int,
    *,
    encoding: str = "utf8",
    max_content_length: int = -1,
    strict: bool = True,
) -> MultiDict:
    if not content_length:
        return MultiDict()

    if max_content_length > 0 and content_length > max_content_length:
        raise RequestEntityTooLarge("Maximum content length exceeded.")

    content_type, options = parse_options_header(content_type)
    encoding = options.get("charset", encoding)

    if content_type == "multipart/form-data":
        return parse_multipart(
            stream,
            content_length,
            options,
            encoding=encoding,
            strict=strict,
        )

    content = _read_content(stream, max_content_length, encoding)
    _validate_actual_content_length(content, content_length)

    if content_type in (
        "application/x-www-form-urlencoded",
        "application/x-url-encoded",
    ):
        return parse_query_string(content, encoding=encoding, strict=strict)

    # application/json
    if content_type.startswith("application/json"):
        return parse_json(content, strict=strict)

    raise UnsupportedMediaType("Unsupported Content-Type")


def parse_multipart(
    stream: t.IO[bytes],
    content_length: int,
    options: dict,
    *,
    encoding: str,
    strict: bool = True,
    disk_limit: int = 2 ** 30,
    mem_limit: int = 2 ** 20,
    memfile_limit: int = 2 ** 18,
    buffer_size: int = 2 ** 16,
) -> MultiDict:
    boundary = options.get("boundary", "")
    if not boundary:
        raise MultipartError("No boundary for multipart/form-data.")

    form, files = MultiDict(), MultiDict()
    try:
        mp = MultipartParser(
            stream,
            boundary,
            content_length,
            encoding=encoding,
            disk_limit=disk_limit,
            mem_limit=mem_limit,
            memfile_limit=memfile_limit,
            buffer_size=buffer_size,
        )
        for part in mp:
            if not part.name:
                continue

            if part.filename or not part.is_buffered():
                files.append(part.name, part)
            else:
                form.append(
                    part.name,
                    _normalize_newlines(part.value),
                )

    except MultipartError:
        if strict:
            for part in files.values():
                part.close()
            raise

    form.update(files)
    return form


def parse_query_string(
    query_string: str,
    *,
    encoding: str = "utf8",
    max_query_size: int | None = None,
    strict: bool = True,
) -> MultiDict:
    if max_query_size and len(query_string) > max_query_size:
        raise UriTooLong("The query string is too long")

    form = MultiDict()
    try:
        data = parse_qs(query_string, keep_blank_values=True, encoding=encoding)
        for key, values in data.items():
            form.extend(key, values)
    except ValueError:
        if strict:
            raise

    return form


def parse_json(content: str, *, strict: bool = True) -> MultiDict:
    form = MultiDict()
    try:
        data = json.loads(content)
        form.update(data)
    except json.JSONDecodeError as err:
        if strict:
            raise MultipartError(str(err)) from None

    return form


def _normalize_newlines(text: str) -> str:
    r"""
    A multipart text value can use `\r\n`, `\n`, or `\r` as newlines
    and all three versions are valid.
    This function change `\r\n` or `\r` to just `\n`.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _read_content(stream: t.IO[bytes], max_content_length: int, encoding: str) -> str:
    content = stream.read(max_content_length).decode(encoding)
    if stream.read(1):  # OMG there is still more.
        raise RequestEntityTooLarge("Increase max_content_length.")
    return content


def _validate_actual_content_length(content: str, content_length: int) -> None:
    actual_content_length = len(content)
    if actual_content_length > content_length:
        raise BadRequest("Body is bigger than the declared Content-Length.")
    elif actual_content_length < content_length:
        raise BadRequest("Body is smaller than the declared Content-Length.")
