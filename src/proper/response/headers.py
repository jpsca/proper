import typing as t


class ResponseHeaders:
    """Response headers.
    """

    def set(self):
        pass

    def _get_value(self, header) -> str:
        return ", ".join([
            self._segment_to_str(value, params)
            for value, params in header
        ])

    def _segment_to_str(self, value: str | None, params: dict[str, t.Any]) -> str:
        """Produce a header value and `key=value` parameters separated by semicolons.

        If a value contains non-token characters, it will be quoted.
        If a value is `None`, the parameter is skipped.
        In some keys for some headers, a UTF-8 value can be encoded using a special
        `key*=UTF-8''value` form, where `value` is percent encoded. This function will
        not produce that format automatically, but if a given key ends with an asterisk
        `*`, the value is assumed to have that form and will not be quoted further.
        If a key ends with `*`, its value will not be quoted.

        """
        segments = []
        if value is not None:
            segments.append(value)

        for key, value in params.items():
            if value is None:
                continue
            if key[-1] == "*":
                segments.append(f"{key}={value}")
            else:
                value = self._quote_value(value)
                segments.append(f"{key}={value}")

        return ";".join(segments)

    def _quote_value(self, value: str) -> str:
        """Add double quotes around a header value. If the header contains
        only ASCII token characters, it will be returned unchanged.
        If the header contains ``"`` or ``\\`` characters, they will be escaped
        with an additional ``\\`` character.
        """
        if not value:
            return '""'

        if " " in value or "\\" in value or '"' in value:
            value = value.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{value}"'

        return value
