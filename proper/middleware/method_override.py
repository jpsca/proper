from ..constants import DELETE, PATCH, POST, PUT


__all__ = ("method_override",)


def method_override(req, resp, app):
    """Overrides the request's `POST` method with the method defined in
    the `_method` request parameter or in the `X-HTTP-Method-Override`
    header.

    The `POST` method can be overridden only by these HTTP methods:
    * `PUT`
    * `PATCH`
    * `DELETE`

    """
    if req.method != POST:
        return

    new_method = req.query.get("_method")
    if not new_method:
        new_method = req.headers.get("X_HTTP_METHOD_OVERRIDE")

    new_method = (new_method or "").upper()
    if new_method not in (PUT, PATCH, DELETE):
        return

    req.real_method = POST
    req.method = new_method
