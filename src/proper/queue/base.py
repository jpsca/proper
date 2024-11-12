from huey.api import Huey as BaseQueue


class NoQueue(BaseQueue):
    def __init__(self, **kwargs):
        kwargs["immediate"] = True
        kwargs["immediate_use_memory"] = True
        super().__init__(**kwargs)
