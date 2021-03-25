class Representable:
    __repr_by__ = []
    __repr_max_length__ = 64

    def __repr__(self):
        _id = getattr(self, "id", None)
        attrs = repr_attrs(self) if self.__repr_by__ else None

        return "<{} #{}{}>".format(
            self.__class__.__name__,
            _id or "?",
            f" {attrs}" if attrs else "",
        )


def repr_attrs(self):
    max_length = self.__repr_max_length__
    values = []
    single = len(self.__repr_by__) == 1

    for key in self.__repr_by__:
        value = getattr(self, key, None)
        if value is None:
            continue
        wrap_in_quote = isinstance(value, str)
        value = str(value)
        if len(value) > max_length:
            value = value[:max_length] + "..."
        if wrap_in_quote:
            value = "'{}'".format(value)
        values.append(value if single else "{}:{}".format(key, value))

    return " ".join(values)
