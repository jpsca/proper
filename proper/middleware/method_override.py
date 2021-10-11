from ..constants import DELETE, PATCH, POST, PUT


__all__ = ("method_override",)


def method_override(req, resp, app):
    """Overrides the request's `POST` method with the method defined in
    the `X-HTTP-Method-Override` header or the `_method` parameter in the
    path or in the request body.

    The `POST` method can be overridden only by these HTTP methods:
    * `PUT`
    * `PATCH`
    * `DELETE`

    """
    if req.method != POST:
        return

    new_method = req.headers.get("X_HTTP_METHOD_OVERRIDE")
    if not new_method:
        new_method = req.query.get("_method") or req.form.get("_method")

    new_method = (new_method or "").upper()
    if new_method not in (PUT, PATCH, DELETE):
        return

    req.real_method = POST
    req.method = new_method
