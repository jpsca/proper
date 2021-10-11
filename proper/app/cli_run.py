import multiprocessing
import subprocess
from pathlib import Path


UWSGI_DEV_CONFIG = "uwsgi-dev.ini"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 2300
PACKAGE_JSON = "static/package.json"


def run_server(self):
    """Runs the development server and the assets watchers.

    Read the uWSGI config from `uwsgi-dev.ini` and tries to run
    `npm run watch` in the background if it founds a
    `static/package.json` file.
    """
    if not Path(UWSGI_DEV_CONFIG).exists():
        print(f"💥 {UWSGI_DEV_CONFIG} not found.")
        print("💥 Check you are in the root folder of your application.")
        return

    package_json = Path(PACKAGE_JSON)
    dw = None
    if package_json.exists():
        dw = multiprocessing.Process(name="npm_watch", target=npm_watch)
        dw.daemon = True
        dw.start()
    else:
        print(f"💥 {PACKAGE_JSON} not found. Skipping.")

    cmd = f"uwsgi --ini {UWSGI_DEV_CONFIG}"
    print(cmd)
    try:
        subprocess.check_call(cmd, shell=True)
    except KeyboardInterrupt:
        print("\n✨ Goodbye ✨")
    finally:
        if dw:
            dw.join()


def npm_watch():
    cmd = "cd static && npm run watch"
    print(cmd)
    try:
        subprocess.run(cmd, shell=True)
    except KeyboardInterrupt:
        pass
