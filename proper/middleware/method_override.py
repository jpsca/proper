from ..constants import DELETE, PATCH, POST, PUT


__all__ = ("method_override",)


def method_override(request, response, app):
    """Overrides the request's `POST` method with the method defined in
    the `X-HTTP-Method-Override` header or the `_method` parameter in the
    path or in the request body.

    The `POST` method can be overridden only by these HTTP methods:
    * `PUT`
    * `PATCH`
    * `DELETE`

    """
    if request.request_method != POST:
        return

    new_method = request.headers.get("X_HTTP_METHOD_OVERRIDE")
    if not new_method:
        new_method = request.query.get("_method") or request.form.get("_method")

    new_method = (new_method or "").upper()
    if new_method not in (PUT, PATCH, DELETE):
        return

    request.method = new_method
