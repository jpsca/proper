from huey.api import Huey
from huey.api import crontab as huey_crontab


BaseQueue = Huey


class NoQueue(BaseQueue):
    def __init__(self, **kwargs):
        kwargs["immediate"] = True
        kwargs["immediate_use_memory"] = True
        super().__init__(**kwargs)


def crontab(
    minute: str = "*",
    hour: str = "*",
    day: str = "*",
    month: str = "*",
    day_of_week: str = "*",
    strict: bool = False,
):
    """
    A wrapper around the Huey crontab function to fix some common issues.
    """
    for arg in (minute, hour, day, month, day_of_week):
        if arg.startswith("/"):
            arg = f"*{arg}"
        if arg == "*/1":
            arg = "*"

    return huey_crontab(
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
        strict=strict,
    )


crontab.__doc__ = huey_crontab.__doc__
