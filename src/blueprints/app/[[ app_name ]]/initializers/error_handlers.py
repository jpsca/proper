import proper

from ..app import app
from ..views.page import Page


# You can call your own views for handling any kind of exception, not
# only HTTP exceptions but custom ones or even native Python exceptions
# like `ValueError` or a catch-all Exception.
#
# If `app.config.DEBUG = True`, this also will create test routes
# (based on the name of the exception class) to preview those pages
# so you can test their design.
app.error_handler(proper.errors.NotFound, Page.not_found)  # /_not_found
app.error_handler(Exception, Page.error)  # /_exception
