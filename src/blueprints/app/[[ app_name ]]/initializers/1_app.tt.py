import subprocess
import sys

from [[ app_name ]].app import app
from [[ app_name ]].cl import AppCL


app.CL = AppCL


@app.on_dev_start
def compile_tailwind():
    from pytailwindcss import get_bin_path

    cmd = [
        str(get_bin_path()),
        "-i",
        "static_src/css/app.css",
        "-o",
        "static/css/app.css",
        "--watch",
    ]
    scmd = " ".join(cmd)
    print("Running",f'"{scmd}"')
    subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
