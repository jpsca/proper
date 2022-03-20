from ..constants import FLASHES_SESSION_KEY


ALERT = "alert"
ERROR = "error"
NOTICE = "notice"
DICT_ATTRS = ("keys", "get", "items", "update", "setdefault", "values")


class FlashDict:
    def __init__(self, response):
        self.response = response

    @property
    def dict(self):
        if FLASHES_SESSION_KEY not in self.response.session:
            self.response.session[FLASHES_SESSION_KEY] = {}
        return self.response.session[FLASHES_SESSION_KEY]

    def __getattr__(self, name):
        if name in DICT_ATTRS:
            return getattr(self.dict, name)
        return super().__getattr__(name)

    def __setitem__(self, key, value):
        self.dict[key] = value

    def __delitem__(self, key):
        self.dict.__delitem__(key)

    def __contains__(self, key):
        return key in self.dict

    def alert(self, message):
        self[ALERT] = message

    def error(self, message):
        self[ERROR] = message

    def notice(self, message):
        self[NOTICE] = message
