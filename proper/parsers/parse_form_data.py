"""
## proper.parsers.parse_form_data

"""
from multipart import MultipartParser
from multipart import parse_options_header
from multipart import parse_qs
import ujson

from .. import errors
from ..support import MultiDict


__all__ = ("parse_form_data",)


def parse_form_data(stream, content_type, content_length, encoding="utf8", config=None):
    config = config or {}
    max_content_length = config.get("max_content_length")
    max_memory_size = config.get("max_memory_size")

    if max_content_length and content_length > max_content_length:
        raise errors.RequestEntityTooLarge("Maximum content length exceeded.")

    content_type, options = parse_options_header(content_type)
    encoding = options.get("charset", encoding)

    # multipart/form-data
    if content_type.startswith("multipart/"):
        boundary = options.get("boundary", "")
        if not boundary:
            raise errors.BadRequest("No boundary for multipart/form-data.")

        return parse_multipart(stream, content_length, encoding, boundary)

    if max_memory_size and content_length > max_memory_size:
        raise errors.RequestEntityTooLarge("Increase max_memory_size.")

    content = stream.read(max_memory_size).decode(encoding)

    if stream.read(1):  # OMG there is still more.
        raise errors.RequestEntityTooLarge("Increase max_memory_size.")

    actual_content_length = len(content)

    if actual_content_length > content_length:
        raise errors.BadRequest("Body is bigger than the declared Content-Length.")
    elif actual_content_length < content_length:
        raise errors.BadRequest("Body is smaller than the declared Content-Length.")

    form = MultiDict()

    # application/x-www-form-urlencoded
    # application/x-url-encoded
    if content_type.startswith("application/x-"):
        data = parse_qs(content, keep_blank_values=True)
        for key, values in data.items():
            form[key] = [True if value == "" else value for value in values]
        return form

    # application/json
    if content_type.startswith("application/json"):
        data = ujson.loads(content)
        for key, values in data.items():
            form[key] = values
        return form

    raise errors.UnsupportedMediaType("Unsupported Content-Type")


def parse_multipart(stream, content_length, encoding, boundary, **kwargs):
    form = MultiDict()
    kwargs["charset"] = encoding

    for part in MultipartParser(stream, boundary, content_length, **kwargs):
        if part.filename:
            form[part.name].append(part)
        else:
            form[part.name].append(normalize_newlines(part.value))

    return form


def normalize_newlines(text):
    r"""A multipart text value can use `\r\n`, `\n`, or `\r` as newlines and
    all three versions are valid.
    This function change `\r\n` or `\r` to just `\n`.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")
