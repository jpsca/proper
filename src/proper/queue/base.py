from huey.api import Huey


class BaseQueue(Huey):
    pass


class NoQueue(BaseQueue):
    def __init__(self, **kwargs):
        kwargs["immediate"] = True
        kwargs["immediate_use_memory"] = True
        super().__init__(**kwargs)
