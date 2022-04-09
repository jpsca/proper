import proper

from ..app import app
from ..controllers import Page


# You can call your own views for handling any kind of exception, not
# only HTTP exceptions but custom ones or even native Python exceptions
# like `ValueError` or a catch-all Exception.
# If `app.config.debug = True`, this also will create routes so can test
# your error pages.
app.error_handler(proper.errors.NotFound, Page.not_found)  # /_not_found
app.error_handler(Exception, Page.error)  # /_exception
