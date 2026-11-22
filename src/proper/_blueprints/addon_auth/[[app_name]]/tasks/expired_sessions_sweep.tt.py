from huey import crontab

from [[app_name]].main import app
from [[app_name]].models import Session


# Daily sweep of the sessions nobody can use anymore: the expired ones
# and the revoked ones. Without it, the `session` table only grows.
#
# Tune `crontab(...)` to taste.
@app.queue.periodic_task(crontab(hour="4", minute="0"))
def sweep_expired_sessions():
    Session.purge_expired()
