from huey import crontab

from proper.rich_text import purge_abandoned_uploads

from [[app_name]].main import app
from [[app_name]].models import Attachment


# Daily sweep of rich-text uploads that were created by the editor but
# never confirmed by a form submission (user closed the tab, etc.).
#
# Tune `crontab(...)` and `grace_hours=` to taste. Setting `grace_hours`
# too low risks purging a legitimate upload that the user is still
# composing; too high lets storage accumulate orphans.
@app.queue.periodic_task(crontab(hour="3", minute="0"))
def sweep_rich_text_uploads():
    purge_abandoned_uploads(Attachment, grace_hours=24)
