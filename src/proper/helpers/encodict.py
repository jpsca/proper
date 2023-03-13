import typing as t


class EncoDict(dict):
    """A `dict` subclas that runs its `encode_key` method on a key
    before using it."""

    def encode_key(self, key: str) -> str:
        return key

    def __contains__(self, key: str):
        key = self.encode_key(key)
        return super().__contains__(key)

    def __delitem__(self, key: str):
        key = self.encode_key(key)
        return super().__delitem__(key)

    def __getitem__(self, key: str):
        key = self.encode_key(key)
        return super().__getitem__(key)

    def __setitem__(self, key: str, value: t.Any):
        key = self.encode_key(key)
        return super().__setitem__(key, value)

    def get(self, key: str, default: t.Any = None) -> t.Any:
        key = self.encode_key(key)
        return super().get(key, default)

    def setdefault(self, key: str, default: t.Any = None) -> t.Any:
        key = self.encode_key(key)
        return super().setdefault(key, default)

    def update(self, dict_or_iter = None, **kwargs):
        if dict_or_iter:
            for key in dict(dict_or_iter):
                self[key] = dict_or_iter[key]

        for key in kwargs:
            self[key] = kwargs[key]
