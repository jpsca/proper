import json

import multipart

from .. import errors
from ..helpers import MultiDict


__all__ = ("parse_form_data",)


def parse_form_data(
    stream,
    content_type,
    content_length,
    encoding="utf8",
    config=None,
):
    config = config or {}
    try:
        return _parse_form_data(
            stream,
            content_type,
            content_length,
            encoding,
            config,
        )
    except ValueError:
        raise errors.BadRequest()


def _parse_form_data(
    stream,
    content_type,
    content_length,
    encoding,
    config,
):
    max_content_length = config.get("max_content_length")
    validate_max_content_length(content_length, max_content_length)
    content_type, options = multipart.parse_options_header(content_type)
    encoding = options.get("charset", encoding)

    # multipart/form-data
    if content_type.startswith("multipart/"):
        return parse_multipart(stream, content_length, encoding, options)

    content = read_content(stream, max_content_length, encoding)
    validate_actual_content_length(content, content_length)

    # application/x-www-form-memory
    # application/x-url-encoded
    if content_type.startswith("application/x-"):
        return parse_qs(content)

    # application/json
    if content_type.startswith("application/json"):
        return parse_json(content)

    raise errors.UnsupportedMediaType("Unsupported Content-Type")


def validate_max_content_length(content_length, max_content_length):
    if max_content_length and content_length > max_content_length:
        raise errors.RequestEntityTooLarge("Maximum content length exceeded.")


def parse_multipart(stream, content_length, encoding, options):
    boundary = get_boundary(options)
    form = MultiDict()
    parser = multipart.MultipartParser(
        stream, boundary, content_length, charset=encoding
    )
    for part in parser:
        if part.filename:
            form[part.name].append(part)
        else:
            form[part.name].append(normalize_newlines(part.value))
    return form


def get_boundary(options):
    boundary = options.get("boundary", "")
    if not boundary:
        raise errors.BadRequest("No boundary for multipart/form-data.")
    return boundary


def read_content(stream, max_content_length, encoding):
    content = stream.read(max_content_length).decode(encoding)
    if stream.read(1):  # OMG there is still more.
        raise errors.RequestEntityTooLarge("Increase max_content_length.")
    return content


def validate_actual_content_length(content, content_length):
    actual_content_length = len(content)
    if actual_content_length > content_length:
        raise errors.BadRequest("Body is bigger than the declared Content-Length.")
    elif actual_content_length < content_length:
        raise errors.BadRequest("Body is smaller than the declared Content-Length.")


def parse_qs(content):
    form = MultiDict()
    data = multipart.parse_qs(content, keep_blank_values=True)
    for key, values in data.items():
        form[key] = [(True if value == "" else value) for value in values]
    return form


def parse_json(content):
    form = MultiDict()
    data = json.loads(content)
    for key, value in data.items():
        form[key] = [value]
    return form


def normalize_newlines(text):
    r"""A multipart text value can use `\r\n`, `\n`, or `\r` as newlines and
    all three versions are valid.
    This function change `\r\n` or `\r` to just `\n`.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")
