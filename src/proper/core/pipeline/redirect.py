import typing as t


if t.TYPE_CHECKING:
    from proper import Request, Response
    from proper.helpers import Proxy


__all__ = ("redirect",)


def redirect(_app, request: "Request", response: "Response") -> "Response | Proxy | None":
    """If a matched route is a redirect sets the header and response body
    for that redirect to happen and stop further process of the response.
    """
    route = request.matched_route
    if not route:
        return

    if route.redirect:
        params = request.matched_params or {}
        response.redirect_to(
            route.redirect.format(**params),
            status=route.redirect_status,
        )
        return response
