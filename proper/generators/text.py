from pathlib import Path

from ..helpers.render import append_to_file, call, copy_file


TRIX_INSTALL = "npm install trix --no-audit --no-fund"
CSS_FROM = "static/node_modules/trix/dist/trix.css"
CSS_TO = "static/src/css/trix.css"

APPLICATION_CSS = "static/src/css/application.css"
CSS_IMPORT = '@import "./trix.css";'
APPLICATION_JS = "static/src/js/application.js"
JS_IMPORT = 'import "node_modules/trix/dist/trix.js"\n'


def install_proper_text(app):
    call(TRIX_INSTALL)
    root_path = Path(app.root_path.parent)
    copy_file(root_path / CSS_FROM, root_path, CSS_TO)
    append_to_file(root_path, APPLICATION_CSS, CSS_IMPORT)
    append_to_file(root_path, APPLICATION_JS, JS_IMPORT)
